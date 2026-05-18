"""Tests for tools/inspections.py — inspect_package tool."""

import pytest

from appian_deployment_mcp.config import EnvironmentConfig
from appian_deployment_mcp.tools import inspections as insp_module


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


SAMPLE_INSPECTION_RESPONSE = {
    "uuid": "insp-uuid-001",
    "url": "https://mysite.appiancloud.com/suite/deployment-management/v2/inspections/insp-uuid-001",
}


class TestInspectPackage:
    """Tests for the inspect_package tool function."""

    @pytest.mark.asyncio
    async def test_returns_inspection_uuid_and_url(
        self, monkeypatch, default_envs, tmp_path
    ):
        """Successful POST returns the inspection UUID and URL."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        pkg_file = tmp_path / "app.zip"
        pkg_file.write_bytes(b"PK\x03\x04fake-zip-content")

        captured = {}

        async def fake_post_multipart(self, path, json_part, files):
            captured["path"] = path
            captured["json_part"] = json_part
            captured["file_keys"] = list(files.keys())
            return SAMPLE_INSPECTION_RESPONSE

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.close", fake_close
        )

        result = await insp_module.inspect_package(str(pkg_file))

        assert captured["path"] == "/inspections"
        assert "zipFile" in captured["file_keys"]
        assert result == SAMPLE_INSPECTION_RESPONSE

    @pytest.mark.asyncio
    async def test_includes_icf_when_customization_file_provided(
        self, monkeypatch, default_envs, tmp_path
    ):
        """When customization_file_path is given, the ICF part is included."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        pkg_file = tmp_path / "app.zip"
        pkg_file.write_bytes(b"PK\x03\x04fake-zip")
        icf_file = tmp_path / "customization.properties"
        icf_file.write_text("key=value")

        captured = {}

        async def fake_post_multipart(self, path, json_part, files):
            captured["file_keys"] = list(files.keys())
            return SAMPLE_INSPECTION_RESPONSE

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.close", fake_close
        )

        result = await insp_module.inspect_package(
            str(pkg_file), customization_file_path=str(icf_file)
        )

        assert "zipFile" in captured["file_keys"]
        assert "ICF" in captured["file_keys"]

    @pytest.mark.asyncio
    async def test_includes_admin_console_settings_when_provided(
        self, monkeypatch, default_envs, tmp_path
    ):
        """When admin_console_settings_file_path is given, it is included."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        pkg_file = tmp_path / "app.zip"
        pkg_file.write_bytes(b"PK\x03\x04fake-zip")
        acs_file = tmp_path / "admin_settings.zip"
        acs_file.write_bytes(b"PK\x03\x04admin-settings")

        captured = {}

        async def fake_post_multipart(self, path, json_part, files):
            captured["file_keys"] = list(files.keys())
            return SAMPLE_INSPECTION_RESPONSE

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.close", fake_close
        )

        result = await insp_module.inspect_package(
            str(pkg_file), admin_console_settings_file_path=str(acs_file)
        )

        assert "zipFile" in captured["file_keys"]
        assert "adminConsoleSettings" in captured["file_keys"]

    @pytest.mark.asyncio
    async def test_error_when_package_file_missing(self, monkeypatch, default_envs):
        """Returns error dict when the package file does not exist."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        result = await insp_module.inspect_package("/nonexistent/path/app.zip")

        assert result["error"] is True
        assert "/nonexistent/path/app.zip" in result["message"]

    @pytest.mark.asyncio
    async def test_error_when_customization_file_missing(
        self, monkeypatch, default_envs, tmp_path
    ):
        """Returns error dict when the customization file does not exist."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        pkg_file = tmp_path / "app.zip"
        pkg_file.write_bytes(b"PK\x03\x04fake-zip")

        result = await insp_module.inspect_package(
            str(pkg_file), customization_file_path="/nonexistent/custom.properties"
        )

        assert result["error"] is True
        assert "/nonexistent/custom.properties" in result["message"]

    @pytest.mark.asyncio
    async def test_error_when_admin_console_settings_file_missing(
        self, monkeypatch, default_envs, tmp_path
    ):
        """Returns error dict when the admin console settings file does not exist."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        pkg_file = tmp_path / "app.zip"
        pkg_file.write_bytes(b"PK\x03\x04fake-zip")

        result = await insp_module.inspect_package(
            str(pkg_file),
            admin_console_settings_file_path="/nonexistent/admin.zip",
        )

        assert result["error"] is True
        assert "/nonexistent/admin.zip" in result["message"]

    @pytest.mark.asyncio
    async def test_uses_specified_environment(
        self, monkeypatch, default_envs, tmp_path
    ):
        """When environment is provided, the tool resolves that environment."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        pkg_file = tmp_path / "app.zip"
        pkg_file.write_bytes(b"PK\x03\x04fake-zip")

        captured_config = {}

        def fake_init(self, config):
            captured_config["name"] = config.name
            captured_config["domain"] = config.domain

        async def fake_post_multipart(self, path, json_part, files):
            return SAMPLE_INSPECTION_RESPONSE

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.__init__", fake_init
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.close", fake_close
        )

        await insp_module.inspect_package(str(pkg_file), environment="staging")

        assert captured_config["name"] == "staging"
        assert captured_config["domain"] == "staging.appiancloud.com"

    @pytest.mark.asyncio
    async def test_client_closed_on_success(
        self, monkeypatch, default_envs, tmp_path
    ):
        """The client is closed after a successful call."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        pkg_file = tmp_path / "app.zip"
        pkg_file.write_bytes(b"PK\x03\x04fake-zip")

        closed = {"called": False}

        async def fake_post_multipart(self, path, json_part, files):
            return SAMPLE_INSPECTION_RESPONSE

        async def fake_close(self):
            closed["called"] = True

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.close", fake_close
        )

        await insp_module.inspect_package(str(pkg_file))
        assert closed["called"] is True

    @pytest.mark.asyncio
    async def test_client_closed_on_error(
        self, monkeypatch, default_envs, tmp_path
    ):
        """The client is closed even when the POST raises an exception."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        pkg_file = tmp_path / "app.zip"
        pkg_file.write_bytes(b"PK\x03\x04fake-zip")

        closed = {"called": False}

        async def fake_post_multipart(self, path, json_part, files):
            raise RuntimeError("boom")

        async def fake_close(self):
            closed["called"] = True

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.close", fake_close
        )

        with pytest.raises(RuntimeError, match="boom"):
            await insp_module.inspect_package(str(pkg_file))

        assert closed["called"] is True


SAMPLE_COMPLETED_INSPECTION = {
    "status": "COMPLETED",
    "summary": {
        "objectsExpected": {"total": 10, "imported": 8, "failed": 1, "skipped": 1},
        "problems": {
            "totalErrors": 1,
            "totalWarnings": 2,
            "errors": [
                {
                    "errorMessage": "Missing dependency",
                    "objectName": "MyRule",
                    "objectUuid": "obj-uuid-001",
                }
            ],
            "warnings": [
                {
                    "warningMessage": "Deprecated function used",
                    "objectName": "MyInterface",
                    "objectUuid": "obj-uuid-002",
                },
                {
                    "warningMessage": "Unused variable",
                    "objectName": "MyProcess",
                    "objectUuid": "obj-uuid-003",
                },
            ],
        },
    },
}

SAMPLE_IN_PROGRESS_INSPECTION = {
    "status": "IN_PROGRESS",
}


class TestGetInspectionResults:
    """Tests for the get_inspection_results tool function."""

    @pytest.mark.asyncio
    async def test_returns_completed_inspection_results(self, monkeypatch, default_envs):
        """GET returns full results for a COMPLETED inspection."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        captured = {}

        async def fake_get(self, path):
            captured["path"] = path
            return SAMPLE_COMPLETED_INSPECTION

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.close", fake_close
        )

        result = await insp_module.get_inspection_results("insp-uuid-001")

        assert captured["path"] == "/inspections/insp-uuid-001"
        assert result["status"] == "COMPLETED"
        assert result["summary"]["objectsExpected"]["total"] == 10
        assert result["summary"]["problems"]["totalErrors"] == 1
        assert result["summary"]["problems"]["totalWarnings"] == 2
        assert len(result["summary"]["problems"]["errors"]) == 1
        assert len(result["summary"]["problems"]["warnings"]) == 2

    @pytest.mark.asyncio
    async def test_returns_in_progress_status(self, monkeypatch, default_envs):
        """GET returns status for an IN_PROGRESS inspection."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        async def fake_get(self, path):
            return SAMPLE_IN_PROGRESS_INSPECTION

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.close", fake_close
        )

        result = await insp_module.get_inspection_results("insp-uuid-002")

        assert result["status"] == "IN_PROGRESS"
        assert "summary" not in result

    @pytest.mark.asyncio
    async def test_uses_specified_environment(self, monkeypatch, default_envs):
        """When environment is provided, the tool resolves that environment."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        captured_config = {}

        def fake_init(self, config):
            captured_config["name"] = config.name
            captured_config["domain"] = config.domain

        async def fake_get(self, path):
            return SAMPLE_COMPLETED_INSPECTION

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.__init__", fake_init
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.close", fake_close
        )

        await insp_module.get_inspection_results("insp-uuid-001", environment="staging")

        assert captured_config["name"] == "staging"
        assert captured_config["domain"] == "staging.appiancloud.com"

    @pytest.mark.asyncio
    async def test_returns_error_on_api_failure(self, monkeypatch, default_envs):
        """Returns error dict when the API returns an error."""
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
            "appian_deployment_mcp.tools.inspections.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.close", fake_close
        )

        result = await insp_module.get_inspection_results("bad-uuid")

        assert result["error"] is True
        assert result["status_code"] == 404

    @pytest.mark.asyncio
    async def test_client_closed_on_success(self, monkeypatch, default_envs):
        """The client is closed after a successful call."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        closed = {"called": False}

        async def fake_get(self, path):
            return SAMPLE_COMPLETED_INSPECTION

        async def fake_close(self):
            closed["called"] = True

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.close", fake_close
        )

        await insp_module.get_inspection_results("insp-uuid-001")
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
            "appian_deployment_mcp.tools.inspections.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.inspections.AppianClient.close", fake_close
        )

        with pytest.raises(RuntimeError, match="boom"):
            await insp_module.get_inspection_results("insp-uuid-001")

        assert closed["called"] is True
