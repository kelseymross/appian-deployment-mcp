"""Tests for config.py — EnvironmentConfig, load_environments(), and resolve_environment()."""

import os

import pytest

from appian_deployment_mcp.config import EnvironmentConfig, load_environments, resolve_environment


class TestEnvironmentConfig:
    """Tests for the EnvironmentConfig dataclass."""

    def test_base_url(self):
        cfg = EnvironmentConfig(name="default", domain="mysite.appiancloud.com", api_key="k")
        assert cfg.base_url == "https://mysite.appiancloud.com/suite/deployment-management/v2"

    def test_auth_headers_api_key(self):
        cfg = EnvironmentConfig(name="default", domain="d", api_key="my-key")
        assert cfg.auth_headers == {"appian-api-key": "my-key"}

    def test_auth_headers_oauth(self):
        cfg = EnvironmentConfig(name="default", domain="d", oauth_token="tok")
        assert cfg.auth_headers == {"Authorization": "Bearer tok"}

    def test_auth_headers_api_key_takes_precedence(self):
        cfg = EnvironmentConfig(name="default", domain="d", api_key="k", oauth_token="t")
        assert cfg.auth_headers == {"appian-api-key": "k"}

    def test_frozen(self):
        cfg = EnvironmentConfig(name="default", domain="d", api_key="k")
        with pytest.raises(AttributeError):
            cfg.name = "other"


class TestLoadEnvironments:
    """Tests for load_environments()."""

    def test_default_env_with_api_key(self, monkeypatch):
        monkeypatch.setenv("APPIAN_DOMAIN", "mysite.appiancloud.com")
        monkeypatch.setenv("APPIAN_API_KEY", "key123")
        envs = load_environments()
        assert "default" in envs
        cfg = envs["default"]
        assert cfg.name == "default"
        assert cfg.domain == "mysite.appiancloud.com"
        assert cfg.api_key == "key123"
        assert cfg.oauth_token is None

    def test_default_env_with_oauth(self, monkeypatch):
        monkeypatch.setenv("APPIAN_DOMAIN", "mysite.appiancloud.com")
        monkeypatch.setenv("APPIAN_OAUTH_TOKEN", "oauth-tok")
        envs = load_environments()
        cfg = envs["default"]
        assert cfg.api_key is None
        assert cfg.oauth_token == "oauth-tok"

    def test_default_env_api_key_precedence(self, monkeypatch):
        monkeypatch.setenv("APPIAN_DOMAIN", "mysite.appiancloud.com")
        monkeypatch.setenv("APPIAN_API_KEY", "key")
        monkeypatch.setenv("APPIAN_OAUTH_TOKEN", "tok")
        envs = load_environments()
        cfg = envs["default"]
        assert cfg.api_key == "key"
        assert cfg.oauth_token == "tok"

    def test_missing_domain_raises(self, monkeypatch):
        monkeypatch.delenv("APPIAN_DOMAIN", raising=False)
        # Remove any APPIAN_*_DOMAIN vars that might exist
        for key in list(os.environ):
            if key.startswith("APPIAN_") and key.endswith("_DOMAIN"):
                monkeypatch.delenv(key, raising=False)
        with pytest.raises(ValueError, match="Appian domain is required"):
            load_environments()

    def test_missing_credentials_raises(self, monkeypatch):
        monkeypatch.setenv("APPIAN_DOMAIN", "mysite.appiancloud.com")
        monkeypatch.delenv("APPIAN_API_KEY", raising=False)
        monkeypatch.delenv("APPIAN_OAUTH_TOKEN", raising=False)
        with pytest.raises(ValueError, match="Authentication credentials are required"):
            load_environments()

    def test_named_environment(self, monkeypatch):
        monkeypatch.setenv("APPIAN_DEV_DOMAIN", "dev.appiancloud.com")
        monkeypatch.setenv("APPIAN_DEV_API_KEY", "dev-key")
        envs = load_environments()
        assert "dev" in envs
        cfg = envs["dev"]
        assert cfg.name == "dev"
        assert cfg.domain == "dev.appiancloud.com"
        assert cfg.api_key == "dev-key"

    def test_multiple_named_environments(self, monkeypatch):
        monkeypatch.setenv("APPIAN_DOMAIN", "default.appiancloud.com")
        monkeypatch.setenv("APPIAN_API_KEY", "default-key")
        monkeypatch.setenv("APPIAN_PROD_DOMAIN", "prod.appiancloud.com")
        monkeypatch.setenv("APPIAN_PROD_OAUTH_TOKEN", "prod-tok")
        envs = load_environments()
        assert "default" in envs
        assert "prod" in envs
        assert envs["prod"].domain == "prod.appiancloud.com"
        assert envs["prod"].oauth_token == "prod-tok"

    def test_named_env_missing_credentials_raises(self, monkeypatch):
        monkeypatch.setenv("APPIAN_STAGING_DOMAIN", "staging.appiancloud.com")
        monkeypatch.delenv("APPIAN_STAGING_API_KEY", raising=False)
        monkeypatch.delenv("APPIAN_STAGING_OAUTH_TOKEN", raising=False)
        with pytest.raises(ValueError, match="Authentication credentials are required for environment 'staging'"):
            load_environments()


class TestResolveEnvironment:
    """Tests for resolve_environment()."""

    @pytest.fixture()
    def envs(self) -> dict[str, EnvironmentConfig]:
        return {
            "default": EnvironmentConfig(name="default", domain="default.appiancloud.com", api_key="dk"),
            "dev": EnvironmentConfig(name="dev", domain="dev.appiancloud.com", api_key="devk"),
            "prod": EnvironmentConfig(name="prod", domain="prod.appiancloud.com", oauth_token="prodt"),
        }

    def test_resolve_by_name(self, envs):
        cfg = resolve_environment(envs, "dev")
        assert cfg.name == "dev"
        assert cfg.domain == "dev.appiancloud.com"

    def test_resolve_default_when_none(self, envs):
        cfg = resolve_environment(envs, None)
        assert cfg.name == "default"

    def test_resolve_default_when_omitted(self, envs):
        cfg = resolve_environment(envs)
        assert cfg.name == "default"

    def test_resolve_unknown_raises(self, envs):
        with pytest.raises(ValueError, match="Unknown environment 'staging'"):
            resolve_environment(envs, "staging")

    def test_resolve_unknown_lists_available(self, envs):
        with pytest.raises(ValueError, match="Available environments: default, dev, prod"):
            resolve_environment(envs, "staging")

    def test_resolve_no_default_with_none_raises(self):
        envs = {
            "dev": EnvironmentConfig(name="dev", domain="dev.appiancloud.com", api_key="k"),
        }
        with pytest.raises(ValueError, match="Unknown environment 'default'"):
            resolve_environment(envs, None)

    def test_resolve_each_named_env(self, envs):
        for name in envs:
            cfg = resolve_environment(envs, name)
            assert cfg is envs[name]
