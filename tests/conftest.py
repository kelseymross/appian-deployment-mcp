"""Shared test fixtures for the Appian Deployment MCP Server tests."""

import httpx
import pytest
import respx

from appian_deployment_mcp.config import EnvironmentConfig


@pytest.fixture
def sample_env_config() -> EnvironmentConfig:
    """A sample EnvironmentConfig using API key auth."""
    return EnvironmentConfig(
        name="default",
        domain="mysite.appiancloud.com",
        api_key="test-api-key-123",
    )


@pytest.fixture
def sample_oauth_config() -> EnvironmentConfig:
    """A sample EnvironmentConfig using OAuth token auth."""
    return EnvironmentConfig(
        name="staging",
        domain="staging.appiancloud.com",
        oauth_token="test-oauth-token-456",
    )


@pytest.fixture
def multi_env_configs(sample_env_config, sample_oauth_config) -> dict[str, EnvironmentConfig]:
    """A dict of multiple environment configs keyed by name."""
    return {
        sample_env_config.name: sample_env_config,
        sample_oauth_config.name: sample_oauth_config,
    }


@pytest.fixture
def mocked_httpx():
    """Activate respx mock for httpx requests within a test."""
    with respx.mock(assert_all_called=False) as mock:
        yield mock
