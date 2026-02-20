import booboo
from ._scrubber import scrub_headers


def _patch_django_exception_handler():
    """Monkey-patch Django's response_for_exception to capture exceptions
    that Django silently converts to error responses (e.g. DisallowedHost → 400).
    These never propagate to middleware or sys.excepthook."""
    try:
        from django.core.handlers import exception as django_exc

        _original = django_exc.response_for_exception

        def _patched_response_for_exception(request, exc):
            if booboo._client:
                try:
                    request_data, user_data = _extract_django_request(request)
                    booboo._client._capture_and_send(exc, request_data=request_data, user_data=user_data)
                except Exception:
                    pass
            return _original(request, exc)

        django_exc.response_for_exception = _patched_response_for_exception
    except Exception:
        pass


def _extract_django_request(request):
    """Extract request data and user data from a Django HttpRequest."""
    request_data = None
    user_data = None
    try:
        headers = scrub_headers(dict(getattr(request, "headers", {})))
        request_data = {
            "method": request.method,
            "url": request.get_full_path(),
            "headers": headers,
            "query_string": request.META.get("QUERY_STRING", ""),
        }
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            user_data = {}
            if hasattr(user, "pk"):
                user_data["id"] = str(user.pk)
            if hasattr(user, "email") and user.email:
                user_data["email"] = user.email
            if hasattr(user, "username") and user.username:
                user_data["username"] = user.username
        ip = request.META.get("HTTP_X_FORWARDED_FOR")
        if ip:
            ip = ip.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")
        if ip:
            if user_data is None:
                user_data = {}
            user_data["ip_address"] = ip
    except Exception:
        pass
    return request_data, user_data


def _extract_asgi_request(scope):
    """Extract request data and user data from an ASGI scope dict."""
    request_data = None
    user_data = None
    try:
        headers = {}
        for key, value in scope.get("headers", []):
            headers[key.decode("latin-1")] = value.decode("latin-1")
        headers = scrub_headers(headers)

        server = scope.get("server", ("localhost", 80))
        scheme = scope.get("scheme", "http")
        path = scope.get("path", "/")
        qs = scope.get("query_string", b"").decode("utf-8", errors="replace")
        url = f"{scheme}://{server[0]}:{server[1]}{path}"
        if qs:
            url += f"?{qs}"

        request_data = {
            "method": scope.get("method", ""),
            "url": url,
            "headers": headers,
            "query_string": qs,
        }

        client = scope.get("client")
        if client and client[0]:
            user_data = {"ip_address": client[0]}
    except Exception:
        pass
    return request_data, user_data


class BoobooDjangoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as exc:
            if booboo._client:
                request_data, user_data = _extract_django_request(request)
                booboo._client._capture_and_send(exc, request_data=request_data, user_data=user_data)
            raise


class BoobooASGIMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        except Exception as exc:
            if booboo._client:
                request_data, user_data = _extract_asgi_request(scope)
                booboo._client._capture_and_send(exc, request_data=request_data, user_data=user_data)
            raise
