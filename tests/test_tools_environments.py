"""Tests for tools/environments.py — list_environments tool."""

from appian_deployment_mcp.config import EnvironmentConfig
from appian_deployment_mcp.tools import environments as env_module


class TestListEnvironments:
    """Tests for the list_environments tool function."""

    def test_returns_sorted_names(self, monkeypatch):
        envs = {
            "prod": EnvironmentConfig(name="prod", domain="prod.appiancloud.com", api_key="k"),
            "default": EnvironmentConfig(name="default", domain="d.appiancloud.com", api_key="k"),
            "dev": EnvironmentConfig(name="dev", domain="dev.appiancloud.com", api_key="k"),
        }
        monkeypatch.setattr("appian_deployment_mcp.server._environments", envs)
        result = env_module.list_environments()
        assert result == ["default", "dev", "prod"]

    def test_single_environment(self, monkeypatch):
        envs = {
            "default": EnvironmentConfig(name="default", domain="d.appiancloud.com", api_key="k"),
        }
        monkeypatch.setattr("appian_deployment_mcp.server._environments", envs)
        result = env_module.list_environments()
        assert result == ["default"]

    def test_empty_environments(self, monkeypatch):
        monkeypatch.setattr("appian_deployment_mcp.server._environments", {})
        result = env_module.list_environments()
        assert result == []

    def test_returns_list_type(self, monkeypatch):
        envs = {
            "dev": EnvironmentConfig(name="dev", domain="dev.appiancloud.com", api_key="k"),
        }
        monkeypatch.setattr("appian_deployment_mcp.server._environments", envs)
        result = env_module.list_environments()
        assert isinstance(result, list)
