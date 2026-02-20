# Changelog

## 0.7.0 (2026-02-20)

### Features

- Automatic exception capture via `sys.excepthook`
- Manual capture with `booboo.capture_exception()`
- User context with `booboo.set_user()`
- Rich stack traces with source context and local variables
- PII scrubbing for sensitive headers and local variables
- Exception chain support (`__cause__` and `__context__`)
- Framework integrations:
  - **Django**: automatic middleware injection + internal exception capture
  - **Flask**: error handler registration (explicit or monkey-patched)
  - **FastAPI**: ASGI middleware (explicit or monkey-patched)
- Non-blocking event delivery via background threads
- Graceful shutdown with `atexit` flush
