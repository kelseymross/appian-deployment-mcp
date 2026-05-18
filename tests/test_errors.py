"""Tests for errors.py — AppianAPIError, handle_response(), ERROR_MESSAGES, and format_network_error()."""

import httpx
import pytest

from appian_deployment_mcp.errors import (
    ERROR_MESSAGES,
    AppianAPIError,
    format_network_error,
    handle_response,
)


class TestAppianAPIError:
    """Tests for the AppianAPIError exception."""

    def test_stores_status_code_and_message(self):
        err = AppianAPIError(401, "bad creds")
        assert err.status_code == 401
        assert err.message == "bad creds"

    def test_str_includes_status_and_message(self):
        err = AppianAPIError(500, "server error")
        assert str(err) == "HTTP 500: server error"

    def test_is_exception(self):
        assert issubclass(AppianAPIError, Exception)


class TestErrorMessages:
    """Tests for the ERROR_MESSAGES mapping."""

    def test_known_codes_present(self):
        assert set(ERROR_MESSAGES.keys()) == {401, 403, 404, 409}

    def test_401_message(self):
        assert "authentication" in ERROR_MESSAGES[401].lower()

    def test_403_message(self):
        assert "permissions" in ERROR_MESSAGES[403].lower()

    def test_404_message(self):
        assert "not found" in ERROR_MESSAGES[404].lower()

    def test_409_message(self):
        assert "concurrency" in ERROR_MESSAGES[409].lower()


def _make_response(status_code: int, json_body: dict | None = None, text: str = "") -> httpx.Response:
    """Helper to build a fake httpx.Response."""
    if json_body is not None:
        import json
        content = json.dumps(json_body).encode()
        headers = {"content-type": "application/json"}
    else:
        content = text.encode()
        headers = {"content-type": "text/plain"}

    return httpx.Response(
        status_code=status_code,
        content=content,
        headers=headers,
        request=httpx.Request("GET", "https://example.com/test"),
    )


class TestHandleResponse:
    """Tests for handle_response()."""

    def test_2xx_returns_json(self):
        resp = _make_response(200, json_body={"uuid": "abc-123", "status": "COMPLETED"})
        result = handle_response(resp)
        assert result == {"uuid": "abc-123", "status": "COMPLETED"}

    def test_201_returns_json(self):
        resp = _make_response(201, json_body={"created": True})
        result = handle_response(resp)
        assert result == {"created": True}

    def test_401_raises_with_mapped_message(self):
        resp = _make_response(401, text="Unauthorized")
        with pytest.raises(AppianAPIError) as exc_info:
            handle_response(resp)
        assert exc_info.value.status_code == 401
        assert exc_info.value.message == ERROR_MESSAGES[401]

    def test_403_raises_with_mapped_message(self):
        resp = _make_response(403, text="Forbidden")
        with pytest.raises(AppianAPIError) as exc_info:
            handle_response(resp)
        assert exc_info.value.status_code == 403
        assert exc_info.value.message == ERROR_MESSAGES[403]

    def test_404_raises_with_mapped_message(self):
        resp = _make_response(404, text="Not Found")
        with pytest.raises(AppianAPIError) as exc_info:
            handle_response(resp)
        assert exc_info.value.status_code == 404
        assert exc_info.value.message == ERROR_MESSAGES[404]

    def test_409_raises_with_mapped_message(self):
        resp = _make_response(409, text="Conflict")
        with pytest.raises(AppianAPIError) as exc_info:
            handle_response(resp)
        assert exc_info.value.status_code == 409
        assert exc_info.value.message == ERROR_MESSAGES[409]

    def test_unknown_error_includes_raw_body(self):
        resp = _make_response(502, text="Bad Gateway")
        with pytest.raises(AppianAPIError) as exc_info:
            handle_response(resp)
        assert exc_info.value.status_code == 502
        assert "Bad Gateway" in exc_info.value.message

    def test_500_includes_raw_body(self):
        resp = _make_response(500, text="Internal Server Error")
        with pytest.raises(AppianAPIError) as exc_info:
            handle_response(resp)
        assert exc_info.value.status_code == 500
        assert "Internal Server Error" in exc_info.value.message


class TestFormatNetworkError:
    """Tests for format_network_error()."""

    def test_returns_error_dict(self):
        result = format_network_error("mysite.appiancloud.com", ConnectionError("refused"))
        assert result["error"] is True
        assert "message" in result

    def test_message_contains_domain(self):
        result = format_network_error("prod.appiancloud.com", TimeoutError("timed out"))
        assert "prod.appiancloud.com" in result["message"]

    def test_message_contains_error_detail(self):
        err = ConnectionError("Connection refused")
        result = format_network_error("dev.appiancloud.com", err)
        assert "Connection refused" in result["message"]
