import pytest

from booboo._stacktrace import _is_in_app, extract_exception_chain, extract_frames

# --- _is_in_app ---


def test_is_in_app_site_packages():
    assert _is_in_app("/home/user/.venv/lib/python3.12/site-packages/requests/api.py") is False


def test_is_in_app_stdlib():
    assert _is_in_app("/usr/lib/python3.12/json/__init__.py") is False


def test_is_in_app_user_code():
    assert _is_in_app("/home/user/myproject/app.py") is True


# --- extract_frames ---


def _raise_and_extract(fn):
    """Call fn(), catch the exception, extract frames."""
    try:
        fn()
    except Exception as exc:
        return extract_frames(exc)
    pytest.fail("Expected exception")


def test_extract_frames_basic_shape():
    def bad():
        raise ValueError("oops")

    frames = _raise_and_extract(bad)
    assert len(frames) >= 1
    frame = frames[-1]
    assert set(frame.keys()) == {
        "filename",
        "function",
        "lineno",
        "context_line",
        "pre_context",
        "post_context",
        "vars",
        "in_app",
    }


def test_extract_frames_lineno_and_function():
    def bad():
        raise RuntimeError("test")

    frames = _raise_and_extract(bad)
    last = frames[-1]
    assert last["function"] == "bad"
    assert isinstance(last["lineno"], int)
    assert last["lineno"] > 0


def test_extract_frames_context_lines():
    def bad():
        raise TypeError("ctx test")

    frames = _raise_and_extract(bad)
    last = frames[-1]
    assert "raise TypeError" in last["context_line"]
    assert isinstance(last["pre_context"], list)
    assert isinstance(last["post_context"], list)


def test_extract_frames_vars_present():
    def bad():
        x = 42
        raise ValueError(x)

    frames = _raise_and_extract(bad)
    last = frames[-1]
    assert "x" in last["vars"]
    assert last["vars"]["x"] == "42"


def test_extract_frames_in_app():
    def bad():
        raise ValueError("in_app test")

    frames = _raise_and_extract(bad)
    last = frames[-1]
    assert last["in_app"] is True


def test_extract_frames_empty_traceback():
    exc = ValueError("no traceback")
    frames = extract_frames(exc)
    assert frames == []


def test_extract_frames_nested_calls():
    def inner():
        raise RuntimeError("deep")

    def outer():
        inner()

    frames = _raise_and_extract(outer)
    funcs = [f["function"] for f in frames]
    assert "outer" in funcs
    assert "inner" in funcs


# --- extract_exception_chain ---


def test_chain_single_exception():
    try:
        raise ValueError("solo")
    except Exception as exc:
        chain = extract_exception_chain(exc)

    assert len(chain) == 1
    assert chain[0]["type"] == "ValueError"
    assert chain[0]["value"] == "solo"
    assert chain[0]["chain_type"] is None


def test_chain_explicit_cause():
    try:
        try:
            raise KeyError("original")
        except KeyError as orig:
            raise ValueError("wrapper") from orig
    except Exception as exc:
        chain = extract_exception_chain(exc)

    assert len(chain) == 2
    assert chain[0]["type"] == "ValueError"
    assert chain[0]["chain_type"] is None
    assert chain[1]["type"] == "KeyError"
    assert chain[1]["chain_type"] == "cause"


def test_chain_implicit_context():
    try:
        try:
            raise KeyError("original")
        except KeyError:
            raise ValueError("during handling")
    except Exception as exc:
        chain = extract_exception_chain(exc)

    assert len(chain) == 2
    assert chain[0]["type"] == "ValueError"
    assert chain[1]["type"] == "KeyError"
    assert chain[1]["chain_type"] == "context"


def test_chain_suppressed_context():
    try:
        try:
            raise KeyError("original")
        except KeyError:
            raise ValueError("suppressed") from None
    except Exception as exc:
        chain = extract_exception_chain(exc)

    assert len(chain) == 1
    assert chain[0]["type"] == "ValueError"
