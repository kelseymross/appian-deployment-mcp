"""Tests for tools/packages.py — get_application_packages tool."""

import pytest

from appian_deployment_mcp.config import EnvironmentConfig
from appian_deployment_mcp.tools import packages as pkg_module


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


SAMPLE_PACKAGES_RESPONSE = [
    {
        "uuid": "pkg-uuid-1",
        "name": "Package One",
        "description": "First package",
        "objectCount": 10,
        "databaseScriptCount": 2,
        "pluginCount": 1,
        "createdTimestamp": "2024-01-15T10:30:00Z",
    },
    {
        "uuid": "pkg-uuid-2",
        "name": "Package Two",
        "description": "Second package",
        "objectCount": 5,
        "databaseScriptCount": 0,
        "pluginCount": 0,
        "createdTimestamp": "2024-02-20T14:00:00Z",
    },
]


class TestGetApplicationPackages:
    """Tests for the get_application_packages tool function."""

    @pytest.mark.asyncio
    async def test_returns_packages_for_application(self, monkeypatch, default_envs):
        """Successful GET returns the package list from the API."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        captured = {}

        async def fake_get(self, path):
            captured["path"] = path
            return SAMPLE_PACKAGES_RESPONSE

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.packages.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.packages.AppianClient.close", fake_close
        )

        app_uuid = "app-uuid-abc"
        result = await pkg_module.get_application_packages(app_uuid)

        assert captured["path"] == f"/applications/{app_uuid}/packages"
        assert result == SAMPLE_PACKAGES_RESPONSE

    @pytest.mark.asyncio
    async def test_uses_specified_environment(self, monkeypatch, default_envs):
        """When environment is provided, the tool resolves that environment."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        captured_config = {}

        original_init = None

        def fake_init(self, config):
            captured_config["domain"] = config.domain
            captured_config["name"] = config.name

        async def fake_get(self, path):
            return []

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.packages.AppianClient.__init__", fake_init
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.packages.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.packages.AppianClient.close", fake_close
        )

        await pkg_module.get_application_packages("some-uuid", environment="staging")

        assert captured_config["name"] == "staging"
        assert captured_config["domain"] == "staging.appiancloud.com"

    @pytest.mark.asyncio
    async def test_defaults_to_default_environment(self, monkeypatch, default_envs):
        """When no environment is specified, the tool uses the default."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        captured_config = {}

        def fake_init(self, config):
            captured_config["name"] = config.name

        async def fake_get(self, path):
            return []

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.packages.AppianClient.__init__", fake_init
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.packages.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.packages.AppianClient.close", fake_close
        )

        await pkg_module.get_application_packages("some-uuid")

        assert captured_config["name"] == "default"

    @pytest.mark.asyncio
    async def test_returns_error_on_api_failure(self, monkeypatch, default_envs):
        """When the API returns an error, the tool returns the error dict."""
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
            "appian_deployment_mcp.tools.packages.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.packages.AppianClient.close", fake_close
        )

        result = await pkg_module.get_application_packages("bad-uuid")

        assert result["error"] is True
        assert result["status_code"] == 404

    @pytest.mark.asyncio
    async def test_unknown_environment_raises(self, monkeypatch, default_envs):
        """Requesting an unknown environment raises ValueError."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        with pytest.raises(ValueError, match="Unknown environment 'nonexistent'"):
            await pkg_module.get_application_packages(
                "some-uuid", environment="nonexistent"
            )

    @pytest.mark.asyncio
    async def test_client_closed_on_success(self, monkeypatch, default_envs):
        """The client is closed even after a successful call."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        closed = {"called": False}

        async def fake_get(self, path):
            return []

        async def fake_close(self):
            closed["called"] = True

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.packages.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.packages.AppianClient.close", fake_close
        )

        await pkg_module.get_application_packages("some-uuid")
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
            "appian_deployment_mcp.tools.packages.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.packages.AppianClient.close", fake_close
        )

        with pytest.raises(RuntimeError, match="boom"):
            await pkg_module.get_application_packages("some-uuid")

        assert closed["called"] is True
