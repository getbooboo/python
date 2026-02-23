import atexit
import json
import platform
import queue
import sys
import threading
import requests
from ._stacktrace import extract_frames, extract_exception_chain
from ._scrubber import scrub_headers

_SENTINEL = object()


class BoobooClient:
    def __init__(self, dsn, endpoint, environment=""):
        self.dsn = dsn
        self.endpoint = endpoint
        self.environment = environment
        self._orig_excepthook = None
        self._queue = queue.Queue(maxsize=100)
        self._worker = None
        self._worker_started = False
        self._lock = threading.Lock()
        self._user = None
        atexit.register(self._flush)

    def set_user(self, user_data):
        """Set user context for subsequent events."""
        self._user = user_data

    def install(self, app=None):
        """Hook sys.excepthook, auto-detect frameworks, register middleware/handlers."""
        self._orig_excepthook = sys.excepthook
        sys.excepthook = self._excepthook

        # Django: auto-detect -> inject middleware + patch exception handler
        try:
            from django.conf import settings

            mw = "booboo._middleware.BoobooDjangoMiddleware"
            mw_list = list(settings.MIDDLEWARE)
            if mw not in mw_list:
                mw_list.insert(0, mw)
                settings.MIDDLEWARE = mw_list

            from booboo._middleware import _patch_django_exception_handler

            _patch_django_exception_handler()
        except Exception:
            pass

        # Flask: explicit app or auto-patch constructor
        if app is not None and self._is_flask(app):
            self._install_flask(app)
        else:
            try:
                import flask

                self._patch_flask_class(flask.Flask)
            except ImportError:
                pass

        # FastAPI: explicit app or auto-patch constructor
        if app is not None and self._is_fastapi(app):
            self._install_fastapi(app)
        else:
            try:
                import fastapi

                self._patch_fastapi_class(fastapi.FastAPI)
            except ImportError:
                pass

    def _is_flask(self, app):
        try:
            import flask

            return isinstance(app, flask.Flask)
        except ImportError:
            return False

    def _is_fastapi(self, app):
        try:
            import fastapi

            return isinstance(app, fastapi.FastAPI)
        except ImportError:
            return False

    def _install_flask(self, app):
        client = self

        @app.errorhandler(Exception)
        def _booboo_flask_handler(exc):
            request_data = None
            user_data = None
            try:
                from flask import request

                headers = scrub_headers(dict(request.headers))
                request_data = {
                    "method": request.method,
                    "url": request.url,
                    "headers": headers,
                    "query_string": request.query_string.decode("utf-8", errors="replace"),
                }
                if request.remote_addr:
                    user_data = {"ip_address": request.remote_addr}
            except Exception:
                pass
            client._capture_and_send(exc, request_data=request_data, user_data=user_data)
            raise

        return _booboo_flask_handler

    def _install_fastapi(self, app):
        from booboo._middleware import BoobooASGIMiddleware

        app.add_middleware(BoobooASGIMiddleware)

    def _patch_flask_class(self, cls):
        """Monkey-patch Flask.__init__ to auto-register error handler."""
        client = self
        _original_init = cls.__init__

        def _patched_init(self_app, *args, **kwargs):
            _original_init(self_app, *args, **kwargs)
            client._install_flask(self_app)

        cls.__init__ = _patched_init

    def _patch_fastapi_class(self, cls):
        """Monkey-patch FastAPI.__init__ to auto-add ASGI middleware."""
        _original_init = cls.__init__

        def _patched_init(self_app, *args, **kwargs):
            _original_init(self_app, *args, **kwargs)
            from booboo._middleware import BoobooASGIMiddleware

            self_app.add_middleware(BoobooASGIMiddleware)

        cls.__init__ = _patched_init

    def _ensure_worker(self):
        """Lazily start the background worker thread. Returns False if thread creation fails."""
        if self._worker_started:
            return True
        with self._lock:
            if self._worker_started:
                return True
            try:
                self._worker = threading.Thread(target=self._worker_loop, daemon=True)
                self._worker.start()
                self._worker_started = True
                return True
            except RuntimeError:
                return False

    def _worker_loop(self):
        """Background thread: drain queue, send events, exit on sentinel."""
        while True:
            try:
                item = self._queue.get()
                try:
                    if item is _SENTINEL:
                        return
                    self._do_send(item)
                finally:
                    self._queue.task_done()
            except Exception:
                pass

    def _excepthook(self, exc_type, exc_value, exc_tb):
        self._capture_and_send(exc_value)
        if self._orig_excepthook:
            self._orig_excepthook(exc_type, exc_value, exc_tb)

    def capture_exception(self, exc=None):
        """Public API: capture an exception manually."""
        if exc is None:
            exc = sys.exc_info()[1]
        if exc is not None:
            self._capture_and_send(exc)

    def _capture_and_send(self, exc, request_data=None, user_data=None):
        try:
            frames = extract_frames(exc)
        except Exception:
            frames = []

        try:
            exceptions = extract_exception_chain(exc)
        except Exception:
            exceptions = []

        from . import __version__

        context = {
            "sdk": {"name": "booboo-sdk", "version": __version__},
            "runtime": {"name": "Python", "version": platform.python_version()},
        }

        # Merge user: auto-captured user_data takes priority, falls back to set_user()
        user = None
        if self._user:
            user = dict(self._user)
        if user_data:
            if user:
                user.update(user_data)
            else:
                user = user_data
        if user:
            context["user"] = user

        payload = {
            "message": str(exc),
            "exception_type": type(exc).__name__,
            "level": "error",
            "stacktrace": frames,
            "exceptions": exceptions,
            "context": context,
            "tags": {"runtime": "python"},
            "environment": self.environment,
        }
        if request_data:
            payload["request"] = request_data

        try:
            if self._ensure_worker():
                try:
                    self._queue.put_nowait(payload)
                except queue.Full:
                    pass
            else:
                self._do_send(payload)  # sync fallback
        except Exception:
            pass

    def _flush(self):
        """Wait for background worker to drain (called at exit)."""
        try:
            if not self._worker_started:
                return
            self._queue.put_nowait(_SENTINEL)
            self._worker.join(timeout=5)
        except Exception:
            pass

    def _do_send(self, payload):
        try:
            data = json.dumps(payload).encode("utf-8")
            if len(data) > 102_400:
                return  # too large, drop silently
            requests.post(
                self.endpoint,
                data=data,
                headers={"X-Booboo-DSN": self.dsn, "Content-Type": "application/json"},
                timeout=5,
            )
        except Exception:
            pass
