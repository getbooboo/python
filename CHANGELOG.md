# Changelog

## 0.8.0 (2026-02-22)

### Fixed

- **SDK no longer crashes user applications** when thread creation fails (e.g., during interpreter shutdown). Replaced thread-per-event model with a single background worker thread + bounded queue — the same pattern used by Sentry's Python SDK.
- Fixed memory leak: completed thread objects were accumulated indefinitely in long-running processes.
- ASGI middleware no longer crashes on malformed request headers.

### Improved

- Event payloads exceeding 100KB are silently dropped instead of failing on the server.
- Local variable capture limited to 50 per frame to prevent oversized payloads.

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
