import re

SENSITIVE_PATTERN = re.compile(
    r"password|passwd|secret|token|api_key|apikey|access_key|auth|credential|private",
    re.IGNORECASE,
)

SENSITIVE_HEADERS = frozenset({
    "authorization",
    "cookie",
    "set-cookie",
    "x-forwarded-for",
    "x-real-ip",
    "proxy-authorization",
})


def scrub_headers(headers):
    """Scrub sensitive values from HTTP headers."""
    result = {}
    for key, value in headers.items():
        lower = key.lower()
        if lower in SENSITIVE_HEADERS or SENSITIVE_PATTERN.search(lower):
            result[key] = "[filtered]"
        else:
            result[key] = str(value)
    return result


def scrub_vars(local_vars):
    """Filter f_locals: skip dunders, redact sensitive keys, repr+truncate values."""
    result = {}
    for key, value in local_vars.items():
        if key.startswith("__") and key.endswith("__"):
            continue
        if SENSITIVE_PATTERN.search(key):
            result[key] = "[filtered]"
            continue
        try:
            r = repr(value)
        except Exception:
            r = f"<{type(value).__name__}>"
        result[key] = r[:200]
    return result
