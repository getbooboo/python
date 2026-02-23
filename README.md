# booboo-sdk

[![PyPI version](https://img.shields.io/pypi/v/booboo-sdk.svg)](https://pypi.org/project/booboo-sdk/)
[![Python versions](https://img.shields.io/pypi/pyversions/booboo-sdk.svg)](https://pypi.org/project/booboo-sdk/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Official Python SDK for [booboo.dev](https://booboo.dev) error tracking.

## Installation

```bash
pip install booboo-sdk
```

## Quick Start

```python
import booboo

booboo.init("your-dsn-here")
```

That's it. Unhandled exceptions are automatically captured and sent to booboo.dev.

## Manual Capture

```python
try:
    risky_operation()
except Exception:
    booboo.capture_exception()  # captures the current exception
```

Or pass an exception explicitly:

```python
try:
    risky_operation()
except Exception as e:
    booboo.capture_exception(e)
```

## User Context

```python
booboo.set_user({
    "id": "123",
    "email": "user@example.com",
    "username": "alice",
})
```

## Framework Integration

### Django

Auto-detected — no extra setup needed. The SDK injects middleware and patches Django's internal exception handler to capture errors that never reach middleware (like `DisallowedHost`).

### Flask

```python
from flask import Flask
import booboo

app = Flask(__name__)
booboo.init("your-dsn-here", app=app)
```

Or without passing `app` — the SDK monkey-patches `Flask.__init__` to auto-register on any Flask app created after `init()`.

### FastAPI

```python
from fastapi import FastAPI
import booboo

app = FastAPI()
booboo.init("your-dsn-here", app=app)
```

Same auto-detection as Flask if `app` is not passed explicitly.

## Configuration

```python
booboo.init(
    dsn="your-dsn-here",
    endpoint="https://api.booboo.dev/ingest/",  # default
    environment="production",
)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `dsn` | (required) | Your project's DSN from booboo.dev |
| `endpoint` | `https://api.booboo.dev/ingest/` | Ingestion endpoint URL |
| `app` | `None` | Flask/FastAPI app instance for explicit registration |
| `environment` | `""` | Environment name (e.g. `"production"`, `"staging"`). Attached to every event. |

## Features

- Automatic capture of unhandled exceptions
- Rich stack traces with source context and local variables
- Exception chain support (`raise ... from ...`)
- PII scrubbing for sensitive headers and variables
- Django, Flask, and FastAPI integrations
- Non-blocking event delivery
- Graceful shutdown flush
- Minimal dependency footprint (`requests` only)

## License

MIT
