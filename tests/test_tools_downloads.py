"""Tests for tools/downloads.py — download_exported_package tool."""

import pytest

from appian_deployment_mcp.config import EnvironmentConfig
from appian_deployment_mcp.tools import downloads as downloads_module


@pytest.fixture
def default_envs():
    return {
        "default": EnvironmentConfig(
            name="default", domain="mysite.appiancloud.com", api_key="key-123"
        ),
        "staging": EnvironmentConfig(
            name="staging", domain="staging.appiancloud.com", api_key="key-456"
        ),
    }


SAMPLE_EXPORT_RESPONSE = {
    "status": "COMPLETED",
    "packageZip": "https://mysite.appiancloud.com/suite/deployment-management/v2/deployments/export-uuid-001/package.zip",
    "deploymentLogUrl": "https://mysite.appiancloud.com/suite/deployment-management/v2/deployments/export-uuid-001/log",
}


class TestDownloadExportedPackage:
    """Tests for the download_exported_package tool function."""

    @pytest.mark.asyncio
    async def test_successful_download(self, monkeypatch, default_envs, tmp_path):
        """Downloads the package zip and returns file_path and file_size_bytes."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        captured = {}

        async def fake_get(self, path):
            captured["get_path"] = path
            return SAMPLE_EXPORT_RESPONSE

        async def fake_download_file(self, url, save_path):
            captured["download_url"] = url
            captured["save_path"] = save_path
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(b"PK\x03\x04fake-zip-content-here")
            return save_path

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.download_file",
            fake_download_file,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.close", fake_close
        )

        result = await downloads_module.download_exported_package(
            deployment_uuid="export-uuid-001",
            save_directory=str(tmp_path),
        )

        assert captured["get_path"] == "/deployments/export-uuid-001"
        assert captured["download_url"] == SAMPLE_EXPORT_RESPONSE["packageZip"]
        assert result["file_path"] == str(tmp_path / "package.zip")
        assert result["file_size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_error_when_api_returns_error(self, monkeypatch, default_envs):
        """Returns the API error when get deployment results fails."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        error_response = {
            "error": True,
            "status_code": 404,
            "message": "The requested resource was not found. Verify the UUID is correct.",
        }

        async def fake_get(self, path):
            return error_response

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.close", fake_close
        )

        result = await downloads_module.download_exported_package(
            deployment_uuid="nonexistent-uuid"
        )

        assert result["error"] is True
        assert result["status_code"] == 404

    @pytest.mark.asyncio
    async def test_error_when_no_package_zip(self, monkeypatch, default_envs):
        """Returns error when deployment has no packageZip (not a completed export)."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        import_response = {
            "status": "COMPLETED",
            "summary": {"objects": {"total": 5, "imported": 5, "failed": 0, "skipped": 0}},
        }

        async def fake_get(self, path):
            return import_response

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.close", fake_close
        )

        result = await downloads_module.download_exported_package(
            deployment_uuid="import-uuid-001"
        )

        assert result["error"] is True
        assert "not a completed export" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_error_when_in_progress(self, monkeypatch, default_envs):
        """Returns error when deployment is still in progress (no packageZip)."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        async def fake_get(self, path):
            return {"status": "IN_PROGRESS"}

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.close", fake_close
        )

        result = await downloads_module.download_exported_package(
            deployment_uuid="in-progress-uuid"
        )

        assert result["error"] is True
        assert "not a completed export" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_defaults_to_cwd_when_no_save_directory(
        self, monkeypatch, default_envs, tmp_path
    ):
        """Uses current working directory when save_directory is not provided."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)
        monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))

        async def fake_get(self, path):
            return SAMPLE_EXPORT_RESPONSE

        async def fake_download_file(self, url, save_path):
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(b"PK\x03\x04zip-data")
            return save_path

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.download_file",
            fake_download_file,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.close", fake_close
        )

        result = await downloads_module.download_exported_package(
            deployment_uuid="export-uuid-001"
        )

        assert result["file_path"] == str(tmp_path / "package.zip")
        assert result["file_size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_uses_specified_environment(self, monkeypatch, default_envs, tmp_path):
        """Resolves the specified environment for the API call."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        captured_config = {}

        def fake_init(self, config):
            captured_config["name"] = config.name
            captured_config["domain"] = config.domain

        async def fake_get(self, path):
            return SAMPLE_EXPORT_RESPONSE

        async def fake_download_file(self, url, save_path):
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(b"PK\x03\x04zip")
            return save_path

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.__init__", fake_init
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.download_file",
            fake_download_file,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.close", fake_close
        )

        await downloads_module.download_exported_package(
            deployment_uuid="export-uuid-001",
            save_directory=str(tmp_path),
            environment="staging",
        )

        assert captured_config["name"] == "staging"
        assert captured_config["domain"] == "staging.appiancloud.com"

    @pytest.mark.asyncio
    async def test_client_closed_on_success(self, monkeypatch, default_envs, tmp_path):
        """The client is closed after a successful download."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        closed = {"called": False}

        async def fake_get(self, path):
            return SAMPLE_EXPORT_RESPONSE

        async def fake_download_file(self, url, save_path):
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(b"PK\x03\x04zip")
            return save_path

        async def fake_close(self):
            closed["called"] = True

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.download_file",
            fake_download_file,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.close", fake_close
        )

        await downloads_module.download_exported_package(
            deployment_uuid="export-uuid-001",
            save_directory=str(tmp_path),
        )
        assert closed["called"] is True

    @pytest.mark.asyncio
    async def test_client_closed_on_error(self, monkeypatch, default_envs):
        """The client is closed even when the GET raises an exception."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        closed = {"called": False}

        async def fake_get(self, path):
            raise RuntimeError("boom")

        async def fake_close(self):
            closed["called"] = True

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.close", fake_close
        )

        with pytest.raises(RuntimeError, match="boom"):
            await downloads_module.download_exported_package(
                deployment_uuid="export-uuid-001"
            )

        assert closed["called"] is True

    @pytest.mark.asyncio
    async def test_client_closed_when_no_package_zip(self, monkeypatch, default_envs):
        """The client is closed when deployment has no packageZip."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        closed = {"called": False}

        async def fake_get(self, path):
            return {"status": "COMPLETED"}

        async def fake_close(self):
            closed["called"] = True

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.downloads.AppianClient.close", fake_close
        )

        await downloads_module.download_exported_package(
            deployment_uuid="import-uuid"
        )
        assert closed["called"] is True
