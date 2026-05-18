"""Tests for client.py — AppianClient HTTP methods and error handling."""

import json
from pathlib import Path

import httpx
import pytest
import respx

from appian_deployment_mcp.client import AppianClient
from appian_deployment_mcp.config import EnvironmentConfig
from appian_deployment_mcp.errors import AppianAPIError, ERROR_MESSAGES


@pytest.fixture
def config() -> EnvironmentConfig:
    return EnvironmentConfig(
        name="default",
        domain="mysite.appiancloud.com",
        api_key="test-key-123",
    )


@pytest.fixture
def base_url(config: EnvironmentConfig) -> str:
    return config.base_url


@pytest.fixture
async def client(config: EnvironmentConfig):
    c = AppianClient(config)
    yield c
    await c.close()


class TestInit:
    """Tests for AppianClient initialization."""

    def test_sets_base_url(self, config: EnvironmentConfig):
        c = AppianClient(config)
        assert str(c._client.base_url).rstrip("/") == config.base_url

    def test_sets_auth_headers(self, config: EnvironmentConfig):
        c = AppianClient(config)
        assert c._client.headers["appian-api-key"] == "test-key-123"

    def test_sets_timeout(self, config: EnvironmentConfig):
        c = AppianClient(config)
        assert c._client.timeout.connect == 30.0
        assert c._client.timeout.read == 120.0


class TestGet:
    """Tests for AppianClient.get()."""

    async def test_returns_json_on_success(self, client: AppianClient, base_url: str):
        with respx.mock:
            respx.get(f"{base_url}/deployments/abc-123").mock(
                return_value=httpx.Response(200, json={"uuid": "abc-123", "status": "COMPLETED"})
            )
            result = await client.get("/deployments/abc-123")
        assert result == {"uuid": "abc-123", "status": "COMPLETED"}

    async def test_returns_error_dict_on_401(self, client: AppianClient, base_url: str):
        with respx.mock:
            respx.get(f"{base_url}/deployments/abc").mock(
                return_value=httpx.Response(401, text="Unauthorized")
            )
            result = await client.get("/deployments/abc")
        assert result["error"] is True
        assert result["status_code"] == 401
        assert result["message"] == ERROR_MESSAGES[401]

    async def test_returns_error_dict_on_404(self, client: AppianClient, base_url: str):
        with respx.mock:
            respx.get(f"{base_url}/inspections/bad-uuid").mock(
                return_value=httpx.Response(404, text="Not Found")
            )
            result = await client.get("/inspections/bad-uuid")
        assert result["error"] is True
        assert result["status_code"] == 404

    async def test_returns_error_dict_on_unknown_status(self, client: AppianClient, base_url: str):
        with respx.mock:
            respx.get(f"{base_url}/deployments/x").mock(
                return_value=httpx.Response(502, text="Bad Gateway")
            )
            result = await client.get("/deployments/x")
        assert result["error"] is True
        assert result["status_code"] == 502
        assert "Bad Gateway" in result["message"]

    async def test_returns_network_error_on_connect_error(self, client: AppianClient, base_url: str):
        with respx.mock:
            respx.get(f"{base_url}/deployments/x").mock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            result = await client.get("/deployments/x")
        assert result["error"] is True
        assert "mysite.appiancloud.com" in result["message"]

    async def test_returns_network_error_on_timeout(self, client: AppianClient, base_url: str):
        with respx.mock:
            respx.get(f"{base_url}/deployments/x").mock(
                side_effect=httpx.ReadTimeout("Read timed out")
            )
            result = await client.get("/deployments/x")
        assert result["error"] is True
        assert "mysite.appiancloud.com" in result["message"]


class TestPostJson:
    """Tests for AppianClient.post_json()."""

    async def test_sends_json_body_and_returns_response(self, client: AppianClient, base_url: str):
        with respx.mock:
            route = respx.post(f"{base_url}/deployments").mock(
                return_value=httpx.Response(200, json={"uuid": "dep-1", "status": "IN_PROGRESS"})
            )
            result = await client.post_json(
                "/deployments",
                body={"uuids": ["u1"], "exportType": "package"},
                headers={"Action-Type": "export"},
            )
        assert result == {"uuid": "dep-1", "status": "IN_PROGRESS"}
        assert route.calls[0].request.headers["Action-Type"] == "export"
        sent_body = json.loads(route.calls[0].request.content)
        assert sent_body == {"uuids": ["u1"], "exportType": "package"}

    async def test_returns_error_dict_on_api_error(self, client: AppianClient, base_url: str):
        with respx.mock:
            respx.post(f"{base_url}/deployments").mock(
                return_value=httpx.Response(409, text="Conflict")
            )
            result = await client.post_json("/deployments", body={})
        assert result["error"] is True
        assert result["status_code"] == 409

    async def test_returns_network_error_on_connect_error(self, client: AppianClient, base_url: str):
        with respx.mock:
            respx.post(f"{base_url}/deployments").mock(
                side_effect=httpx.ConnectError("refused")
            )
            result = await client.post_json("/deployments", body={})
        assert result["error"] is True
        assert "mysite.appiancloud.com" in result["message"]


class TestPostMultipart:
    """Tests for AppianClient.post_multipart()."""

    async def test_sends_multipart_with_json_and_files(self, client: AppianClient, base_url: str):
        with respx.mock:
            route = respx.post(f"{base_url}/inspections").mock(
                return_value=httpx.Response(200, json={"uuid": "insp-1"})
            )
            result = await client.post_multipart(
                "/inspections",
                json_part={"name": "test-pkg"},
                files={"zipFile": ("pkg.zip", b"fake-zip-content", "application/zip")},
            )
        assert result == {"uuid": "insp-1"}
        # Verify the request was multipart
        request = route.calls[0].request
        assert "multipart/form-data" in request.headers["content-type"]

    async def test_returns_error_dict_on_api_error(self, client: AppianClient, base_url: str):
        with respx.mock:
            respx.post(f"{base_url}/inspections").mock(
                return_value=httpx.Response(403, text="Forbidden")
            )
            result = await client.post_multipart("/inspections", json_part={}, files={})
        assert result["error"] is True
        assert result["status_code"] == 403

    async def test_returns_network_error_on_timeout(self, client: AppianClient, base_url: str):
        with respx.mock:
            respx.post(f"{base_url}/inspections").mock(
                side_effect=httpx.ReadTimeout("timed out")
            )
            result = await client.post_multipart("/inspections", json_part={}, files={})
        assert result["error"] is True
        assert "mysite.appiancloud.com" in result["message"]


class TestDownloadFile:
    """Tests for AppianClient.download_file()."""

    async def test_downloads_and_saves_file(self, client: AppianClient, base_url: str, tmp_path: Path):
        save_path = tmp_path / "output" / "package.zip"
        with respx.mock:
            respx.get(f"{base_url}/downloads/pkg.zip").mock(
                return_value=httpx.Response(200, content=b"zip-file-bytes")
            )
            result = await client.download_file(f"{base_url}/downloads/pkg.zip", save_path)
        assert result == save_path
        assert save_path.read_bytes() == b"zip-file-bytes"

    async def test_creates_parent_directories(self, client: AppianClient, base_url: str, tmp_path: Path):
        save_path = tmp_path / "deep" / "nested" / "dir" / "file.zip"
        with respx.mock:
            respx.get(f"{base_url}/dl/f.zip").mock(
                return_value=httpx.Response(200, content=b"data")
            )
            await client.download_file(f"{base_url}/dl/f.zip", save_path)
        assert save_path.exists()

    async def test_raises_on_http_error(self, client: AppianClient, base_url: str, tmp_path: Path):
        save_path = tmp_path / "out.zip"
        with respx.mock:
            respx.get(f"{base_url}/dl/missing.zip").mock(
                return_value=httpx.Response(404, text="Not Found")
            )
            with pytest.raises(AppianAPIError) as exc_info:
                await client.download_file(f"{base_url}/dl/missing.zip", save_path)
        assert exc_info.value.status_code == 404


class TestGetText:
    """Tests for AppianClient.get_text()."""

    async def test_returns_text_on_success(self, client: AppianClient, base_url: str):
        with respx.mock:
            respx.get(f"{base_url}/deployments/abc/log").mock(
                return_value=httpx.Response(200, text="Deployment log line 1\nLine 2")
            )
            result = await client.get_text("/deployments/abc/log")
        assert result == "Deployment log line 1\nLine 2"

    async def test_returns_error_dict_on_401(self, client: AppianClient, base_url: str):
        with respx.mock:
            respx.get(f"{base_url}/deployments/abc/log").mock(
                return_value=httpx.Response(401, text="Unauthorized")
            )
            result = await client.get_text("/deployments/abc/log")
        assert isinstance(result, dict)
        assert result["error"] is True
        assert result["status_code"] == 401

    async def test_returns_error_dict_on_unknown_status(self, client: AppianClient, base_url: str):
        with respx.mock:
            respx.get(f"{base_url}/deployments/abc/log").mock(
                return_value=httpx.Response(500, text="Internal Server Error")
            )
            result = await client.get_text("/deployments/abc/log")
        assert isinstance(result, dict)
        assert result["error"] is True
        assert result["status_code"] == 500
        assert "Internal Server Error" in result["message"]

    async def test_returns_network_error_on_connect_error(self, client: AppianClient, base_url: str):
        with respx.mock:
            respx.get(f"{base_url}/deployments/abc/log").mock(
                side_effect=httpx.ConnectError("refused")
            )
            result = await client.get_text("/deployments/abc/log")
        assert isinstance(result, dict)
        assert result["error"] is True
        assert "mysite.appiancloud.com" in result["message"]


class TestClose:
    """Tests for AppianClient.close()."""

    async def test_close_does_not_raise(self, config: EnvironmentConfig):
        c = AppianClient(config)
        await c.close()
        # Calling close should not raise
