"""Tests for tools/exports.py — export_package tool."""

import pytest

from appian_deployment_mcp.config import EnvironmentConfig
from appian_deployment_mcp.tools import exports as exports_module


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
    "uuid": "deploy-uuid-1",
    "url": "https://mysite.appiancloud.com/suite/deployment-management/v2/deployments/deploy-uuid-1",
    "status": "IN_PROGRESS",
}


class TestExportPackage:
    """Tests for the export_package tool function."""

    @pytest.mark.asyncio
    async def test_exports_package_successfully(self, monkeypatch, default_envs):
        """Successful POST returns deployment UUID, URL, and status."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        captured = {}

        async def fake_post_multipart(self, path, json_part, files, headers=None):
            captured["path"] = path
            captured["json_part"] = json_part
            captured["files"] = files
            captured["headers"] = headers
            return SAMPLE_EXPORT_RESPONSE

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.exports.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.exports.AppianClient.close", fake_close
        )

        result = await exports_module.export_package(
            uuids=["uuid-1", "uuid-2"],
            export_type="package",
            name="My Export",
            description="Test export",
        )

        assert captured["path"] == "/deployments"
        assert captured["headers"] == {"Action-Type": "export"}
        assert captured["json_part"]["uuids"] == ["uuid-1", "uuid-2"]
        assert captured["json_part"]["exportType"] == "package"
        assert captured["json_part"]["name"] == "My Export"
        assert captured["json_part"]["description"] == "Test export"
        assert captured["files"] == {}
        assert result == SAMPLE_EXPORT_RESPONSE

    @pytest.mark.asyncio
    async def test_exports_application_type(self, monkeypatch, default_envs):
        """export_type 'application' is accepted and sent as exportType."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        captured = {}

        async def fake_post_multipart(self, path, json_part, files, headers=None):
            captured["json_part"] = json_part
            return SAMPLE_EXPORT_RESPONSE

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.exports.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.exports.AppianClient.close", fake_close
        )

        result = await exports_module.export_package(
            uuids=["uuid-1"], export_type="application", name="App Export"
        )

        assert captured["json_part"]["exportType"] == "application"
        assert result == SAMPLE_EXPORT_RESPONSE

    @pytest.mark.asyncio
    async def test_invalid_export_type_returns_error(self, monkeypatch, default_envs):
        """Invalid export_type returns an error dict without calling the API."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        result = await exports_module.export_package(
            uuids=["uuid-1"], export_type="invalid", name="Bad Export"
        )

        assert result["error"] is True
        assert "invalid" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_optional_fields_omitted_when_none(self, monkeypatch, default_envs):
        """When description is not provided, it is not in the json_part."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        captured = {}

        async def fake_post_multipart(self, path, json_part, files, headers=None):
            captured["json_part"] = json_part
            return SAMPLE_EXPORT_RESPONSE

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.exports.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.exports.AppianClient.close", fake_close
        )

        await exports_module.export_package(
            uuids=["uuid-1"], export_type="package", name="My Export"
        )

        assert captured["json_part"]["name"] == "My Export"
        assert "description" not in captured["json_part"]

    @pytest.mark.asyncio
    async def test_uses_specified_environment(self, monkeypatch, default_envs):
        """When environment is provided, the tool resolves that environment."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        captured_config = {}

        def fake_init(self, config):
            captured_config["name"] = config.name
            captured_config["domain"] = config.domain

        async def fake_post_multipart(self, path, json_part, files, headers=None):
            return SAMPLE_EXPORT_RESPONSE

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.exports.AppianClient.__init__", fake_init
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.exports.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.exports.AppianClient.close", fake_close
        )

        await exports_module.export_package(
            uuids=["uuid-1"], export_type="package", name="Staging Export", environment="staging"
        )

        assert captured_config["name"] == "staging"
        assert captured_config["domain"] == "staging.appiancloud.com"

    @pytest.mark.asyncio
    async def test_defaults_to_default_environment(self, monkeypatch, default_envs):
        """When no environment is specified, the tool uses the default."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        captured_config = {}

        def fake_init(self, config):
            captured_config["name"] = config.name

        async def fake_post_multipart(self, path, json_part, files, headers=None):
            return SAMPLE_EXPORT_RESPONSE

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.exports.AppianClient.__init__", fake_init
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.exports.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.exports.AppianClient.close", fake_close
        )

        await exports_module.export_package(
            uuids=["uuid-1"], export_type="package", name="Default Export"
        )

        assert captured_config["name"] == "default"

    @pytest.mark.asyncio
    async def test_returns_error_on_api_failure(self, monkeypatch, default_envs):
        """When the API returns an error, the tool returns the error dict."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        error_response = {
            "error": True,
            "status_code": 409,
            "message": "Concurrency limit reached. Retry the operation after a short delay.",
        }

        async def fake_post_multipart(self, path, json_part, files, headers=None):
            return error_response

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.exports.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.exports.AppianClient.close", fake_close
        )

        result = await exports_module.export_package(
            uuids=["uuid-1"], export_type="package", name="Error Export"
        )

        assert result["error"] is True
        assert result["status_code"] == 409

    @pytest.mark.asyncio
    async def test_unknown_environment_raises(self, monkeypatch, default_envs):
        """Requesting an unknown environment raises ValueError."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        with pytest.raises(ValueError, match="Unknown environment 'nonexistent'"):
            await exports_module.export_package(
                uuids=["uuid-1"], export_type="package", name="Bad Env", environment="nonexistent"
            )

    @pytest.mark.asyncio
    async def test_client_closed_on_success(self, monkeypatch, default_envs):
        """The client is closed even after a successful call."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        closed = {"called": False}

        async def fake_post_multipart(self, path, json_part, files, headers=None):
            return SAMPLE_EXPORT_RESPONSE

        async def fake_close(self):
            closed["called"] = True

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.exports.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.exports.AppianClient.close", fake_close
        )

        await exports_module.export_package(
            uuids=["uuid-1"], export_type="package", name="Close Test"
        )
        assert closed["called"] is True

    @pytest.mark.asyncio
    async def test_client_closed_on_error(self, monkeypatch, default_envs):
        """The client is closed even when post_multipart raises an exception."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        closed = {"called": False}

        async def fake_post_multipart(self, path, json_part, files, headers=None):
            raise RuntimeError("boom")

        async def fake_close(self):
            closed["called"] = True

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.exports.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.exports.AppianClient.close", fake_close
        )

        with pytest.raises(RuntimeError, match="boom"):
            await exports_module.export_package(
                uuids=["uuid-1"], export_type="package", name="Error Test"
            )

        assert closed["called"] is True
