from booboo._scrubber import scrub_headers, scrub_vars

# --- scrub_headers ---


def test_scrub_headers_passes_safe_headers():
    result = scrub_headers({"Content-Type": "application/json", "Accept": "text/html"})
    assert result == {"Content-Type": "application/json", "Accept": "text/html"}


def test_scrub_headers_filters_authorization():
    result = scrub_headers({"Authorization": "Bearer secret123"})
    assert result == {"Authorization": "[filtered]"}


def test_scrub_headers_filters_cookie():
    result = scrub_headers({"Cookie": "session=abc", "Set-Cookie": "session=xyz"})
    assert result == {"Cookie": "[filtered]", "Set-Cookie": "[filtered]"}


def test_scrub_headers_filters_ip_headers():
    result = scrub_headers({"X-Forwarded-For": "1.2.3.4", "X-Real-Ip": "5.6.7.8"})
    assert result == {"X-Forwarded-For": "[filtered]", "X-Real-Ip": "[filtered]"}


def test_scrub_headers_case_insensitive():
    result = scrub_headers({"AUTHORIZATION": "Bearer x", "cookie": "y"})
    assert result == {"AUTHORIZATION": "[filtered]", "cookie": "[filtered]"}


def test_scrub_headers_filters_pattern_match():
    # Pattern matches underscored keys (api_key, auth_token), not hyphenated ones
    result = scrub_headers({"X-Secret-Key": "abc123", "X-Auth-Token": "tok"})
    assert result == {"X-Secret-Key": "[filtered]", "X-Auth-Token": "[filtered]"}


def test_scrub_headers_coerces_values_to_string():
    result = scrub_headers({"Content-Length": 42})
    assert result == {"Content-Length": "42"}


# --- scrub_vars ---


def test_scrub_vars_skips_dunders():
    result = scrub_vars({"__name__": "foo", "__module__": "bar", "x": 1})
    assert "__name__" not in result
    assert "__module__" not in result
    assert "x" in result


def test_scrub_vars_redacts_sensitive_keys():
    result = scrub_vars({"password": "hunter2", "api_key": "sk-123", "name": "tom"})
    assert result["password"] == "[filtered]"
    assert result["api_key"] == "[filtered]"
    assert result["name"] == "'tom'"


def test_scrub_vars_repr_truncates_long_values():
    result = scrub_vars({"data": "x" * 500})
    assert len(result["data"]) <= 200


def test_scrub_vars_handles_repr_failure():
    class BadRepr:
        def __repr__(self):
            raise RuntimeError("boom")

    result = scrub_vars({"obj": BadRepr()})
    assert result["obj"] == "<BadRepr>"


def test_scrub_vars_caps_at_50_keys():
    big = {f"key_{i}": i for i in range(100)}
    result = scrub_vars(big)
    assert len(result) == 50


def test_scrub_vars_sensitive_pattern_case_insensitive():
    result = scrub_vars({"SECRET_TOKEN": "abc", "Password": "xyz"})
    assert result["SECRET_TOKEN"] == "[filtered]"
    assert result["Password"] == "[filtered]"
