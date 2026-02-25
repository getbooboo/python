import json
from unittest.mock import patch

import pytest

from booboo._client import BoobooClient


@pytest.fixture
def client():
    c = BoobooClient("test-dsn-123", "https://example.com/ingest/", environment="testing")
    yield c
    # Drain the queue so the worker thread doesn't leak
    c._flush()


# --- init state ---


def test_client_init_stores_config(client):
    assert client.dsn == "test-dsn-123"
    assert client.endpoint == "https://example.com/ingest/"
    assert client.environment == "testing"


def test_client_default_environment():
    c = BoobooClient("dsn", "https://example.com/ingest/")
    assert c.environment == ""
    c._flush()


# --- set_user ---


def test_set_user(client):
    client.set_user({"id": "42", "email": "test@example.com"})
    assert client._user == {"id": "42", "email": "test@example.com"}


def test_set_user_none(client):
    client.set_user({"id": "42"})
    client.set_user(None)
    assert client._user is None


# --- _capture_and_send payload ---


def test_capture_and_send_payload_shape(client):
    """Verify the payload has the expected top-level keys."""
    payloads = []
    client._do_send = lambda p: payloads.append(p)
    client._ensure_worker = lambda: False  # force sync send

    try:
        raise ValueError("test error")
    except Exception as exc:
        client._capture_and_send(exc)

    assert len(payloads) == 1
    p = payloads[0]
    assert p["message"] == "test error"
    assert p["exception_type"] == "ValueError"
    assert p["level"] == "error"
    assert p["environment"] == "testing"
    assert isinstance(p["stacktrace"], list)
    assert isinstance(p["exceptions"], list)
    assert p["tags"] == {"runtime": "python"}
    assert "sdk" in p["context"]
    assert "runtime" in p["context"]


def test_capture_and_send_sdk_context(client):
    payloads = []
    client._do_send = lambda p: payloads.append(p)
    client._ensure_worker = lambda: False

    try:
        raise ValueError("x")
    except Exception as exc:
        client._capture_and_send(exc)

    ctx = payloads[0]["context"]
    assert ctx["sdk"]["name"] == "booboo-sdk"
    assert ctx["runtime"]["name"] == "Python"


def test_capture_and_send_with_request_data(client):
    payloads = []
    client._do_send = lambda p: payloads.append(p)
    client._ensure_worker = lambda: False

    req = {"method": "GET", "url": "/test", "headers": {}, "query_string": ""}
    try:
        raise ValueError("x")
    except Exception as exc:
        client._capture_and_send(exc, request_data=req)

    assert payloads[0]["request"] == req


def test_capture_and_send_merges_user(client):
    payloads = []
    client._do_send = lambda p: payloads.append(p)
    client._ensure_worker = lambda: False

    client.set_user({"id": "1", "email": "a@b.com"})
    try:
        raise ValueError("x")
    except Exception as exc:
        client._capture_and_send(exc, user_data={"ip_address": "1.2.3.4"})

    user = payloads[0]["context"]["user"]
    assert user["id"] == "1"
    assert user["email"] == "a@b.com"
    assert user["ip_address"] == "1.2.3.4"


def test_capture_and_send_user_data_without_set_user(client):
    payloads = []
    client._do_send = lambda p: payloads.append(p)
    client._ensure_worker = lambda: False

    try:
        raise ValueError("x")
    except Exception as exc:
        client._capture_and_send(exc, user_data={"ip_address": "1.2.3.4"})

    assert payloads[0]["context"]["user"] == {"ip_address": "1.2.3.4"}


def test_capture_and_send_no_user(client):
    payloads = []
    client._do_send = lambda p: payloads.append(p)
    client._ensure_worker = lambda: False

    try:
        raise ValueError("x")
    except Exception as exc:
        client._capture_and_send(exc)

    assert "user" not in payloads[0]["context"]


# --- _do_send ---


@patch("booboo._client.requests.post")
def test_do_send_correct_headers(mock_post, client):
    payload = {"message": "test", "level": "error"}
    client._do_send(payload)

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert call_kwargs.kwargs["headers"] == {
        "X-Booboo-DSN": "test-dsn-123",
        "Content-Type": "application/json",
    }
    assert json.loads(call_kwargs.kwargs["data"]) == payload


@patch("booboo._client.requests.post")
def test_do_send_drops_oversized(mock_post, client):
    payload = {"message": "x" * 200_000}
    client._do_send(payload)
    mock_post.assert_not_called()


@patch("booboo._client.requests.post", side_effect=ConnectionError("fail"))
def test_do_send_swallows_errors(mock_post, client):
    # Should not raise
    client._do_send({"message": "test"})


# --- capture_exception ---


def test_capture_exception_explicit(client):
    payloads = []
    client._do_send = lambda p: payloads.append(p)
    client._ensure_worker = lambda: False

    exc = ValueError("explicit")
    exc.__traceback__ = None
    client.capture_exception(exc)

    assert len(payloads) == 1
    assert payloads[0]["message"] == "explicit"


def test_capture_exception_implicit(client):
    payloads = []
    client._do_send = lambda p: payloads.append(p)
    client._ensure_worker = lambda: False

    try:
        raise RuntimeError("implicit")
    except RuntimeError:
        client.capture_exception()

    assert len(payloads) == 1
    assert payloads[0]["message"] == "implicit"


def test_capture_exception_none_outside_handler(client):
    payloads = []
    client._do_send = lambda p: payloads.append(p)
    client._ensure_worker = lambda: False

    client.capture_exception(None)
    assert len(payloads) == 0
