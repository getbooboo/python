from ._client import BoobooClient

__version__ = "0.7.0"

_client = None


def init(dsn, endpoint="https://api.booboo.dev/ingest/", app=None):
    """Initialize booboo error tracking.

    Always hooks sys.excepthook. Auto-detects Django, Flask, and FastAPI.
    Pass app= to explicitly register with a specific app instance.
    """
    global _client
    _client = BoobooClient(dsn, endpoint)
    _client.install(app)


def capture_exception(exc=None):
    """Manually capture an exception. Uses sys.exc_info() if exc is None."""
    if _client:
        _client.capture_exception(exc)


def set_user(user_data):
    """Set user context (id, email, username, ip_address, etc.) for subsequent events."""
    if _client:
        _client.set_user(user_data)
