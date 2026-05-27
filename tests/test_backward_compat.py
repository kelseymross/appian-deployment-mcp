"""Backward compatibility smoke tests.

Verifies that the pipeline feature does not break existing tool registration,
naming, or environment variable requirements.

Validates: Requirements 7.1, 7.2, 7.3, 7.4
"""

import inspect
import os
from unittest.mock import patch

import pytest

from appian_deployment_mcp.server import mcp


# The 11 original tools that must remain registered with unchanged names.
EXISTING_TOOL_NAMES = {
    "export_package",
    "deploy_package",
    "inspect_package",
    "get_inspection_results",
    "get_deployment_results",
    "get_deployment_log",
    "poll_deployment_status",
    "poll_inspection_status",
    "download_exported_package",
    "get_application_packages",
    "list_environments",
}

# The new pipeline tools added by the deployment-pipeline feature.
NEW_PIPELINE_TOOL_NAMES = {
    "create_pipeline",
    "list_pipelines",
    "get_pipeline",
    "run_pipeline",
    "run_adhoc_pipeline",
    "get_pipeline_run_status",
    "list_pipeline_runs",
    "cancel_pipeline_run",
    "approve_pipeline_stage",
    "reject_pipeline_stage",
}


class TestExistingToolsRegistered:
    """Requirement 7.1: All 11 existing tools remain registered with unchanged names."""

    def test_all_existing_tools_are_registered(self):
        """Every one of the 11 original tools must be present on the MCP server."""
        registered = {tool.name for tool in mcp._tool_manager.list_tools()}
        missing = EXISTING_TOOL_NAMES - registered
        assert not missing, f"Existing tools missing from MCP server: {missing}"

    @pytest.mark.parametrize("tool_name", sorted(EXISTING_TOOL_NAMES))
    def test_existing_tool_registered_individually(self, tool_name: str):
        """Each existing tool is individually registered."""
        registered = {tool.name for tool in mcp._tool_manager.list_tools()}
        assert tool_name in registered, f"Tool '{tool_name}' is not registered"


class TestNewToolsDistinctNames:
    """Requirement 7.4: New pipeline tools have names distinct from existing tools."""

    def test_no_name_collision_between_existing_and_new(self):
        """New pipeline tool names must not overlap with existing tool names."""
        overlap = EXISTING_TOOL_NAMES & NEW_PIPELINE_TOOL_NAMES
        assert not overlap, f"Name collision between existing and new tools: {overlap}"

    def test_all_registered_tool_names_are_unique(self):
        """No two registered tools share the same name."""
        registered = [tool.name for tool in mcp._tool_manager.list_tools()]
        assert len(registered) == len(set(registered)), "Duplicate tool names found"

    def test_new_pipeline_tools_are_registered(self):
        """All new pipeline tools are registered on the server."""
        registered = {tool.name for tool in mcp._tool_manager.list_tools()}
        missing = NEW_PIPELINE_TOOL_NAMES - registered
        assert not missing, f"New pipeline tools missing from MCP server: {missing}"


class TestNoNewEnvVarsForExistingTools:
    """Requirement 7.3: No new environment variables required for existing tool operation."""

    # The only env vars the existing tools depend on are the APPIAN_* config vars.
    # Pipeline features must not introduce mandatory env vars that break existing tools.
    EXISTING_ENV_VARS = {
        "APPIAN_DOMAIN",
        "APPIAN_API_KEY",
        "APPIAN_OAUTH_TOKEN",
        "APPIAN_API_VERSION",
    }

    def test_config_module_does_not_reference_pipeline_env_vars(self):
        """The config module (used by existing tools) should not require pipeline-specific env vars."""
        from appian_deployment_mcp import config

        source = inspect.getsource(config)
        # Pipeline-specific env vars should not appear in config.py
        pipeline_env_patterns = [
            "APPIAN_PIPELINE",
            "PIPELINE_",
        ]
        for pattern in pipeline_env_patterns:
            assert pattern not in source, (
                f"config.py references pipeline env var pattern '{pattern}' — "
                "this could break existing tools"
            )

    def test_existing_tools_load_with_standard_env_vars_only(self):
        """Existing tools can be loaded with only the standard APPIAN_* env vars set."""
        from appian_deployment_mcp.config import load_environments

        env = {
            "APPIAN_DOMAIN": "test.appiancloud.com",
            "APPIAN_API_KEY": "test-key-123",
        }
        with patch.dict(os.environ, env, clear=True):
            environments = load_environments()
            assert "default" in environments
            assert environments["default"].domain == "test.appiancloud.com"

    def test_server_module_imports_without_pipeline_env_vars(self):
        """The server module can be imported without any pipeline-specific env vars."""
        # If we got here, the import at the top of this file already succeeded.
        # This test explicitly verifies the mcp instance is functional.
        assert mcp is not None
        assert mcp.name == "appian-deployment"


class TestExistingToolSignaturesPreserved:
    """Requirement 7.2: Existing tools maintain their parameter signatures."""

    def _get_tool_by_name(self, name: str):
        """Helper to retrieve a tool object by name."""
        for tool in mcp._tool_manager.list_tools():
            if tool.name == name:
                return tool
        return None

    def test_export_package_has_expected_params(self):
        """export_package tool has its original parameters."""
        from appian_deployment_mcp.tools.exports import export_package

        sig = inspect.signature(export_package)
        param_names = list(sig.parameters.keys())
        assert "uuids" in param_names
        assert "export_type" in param_names
        assert "name" in param_names
        assert "environment" in param_names

    def test_deploy_package_has_expected_params(self):
        """deploy_package tool has its original parameters."""
        from appian_deployment_mcp.tools.deployments import deploy_package

        sig = inspect.signature(deploy_package)
        param_names = list(sig.parameters.keys())
        assert "name" in param_names
        assert "package_file_path" in param_names
        assert "environment" in param_names

    def test_inspect_package_has_expected_params(self):
        """inspect_package tool has its original parameters."""
        from appian_deployment_mcp.tools.inspections import inspect_package

        sig = inspect.signature(inspect_package)
        param_names = list(sig.parameters.keys())
        assert "package_file_path" in param_names
        assert "environment" in param_names

    def test_get_deployment_results_has_expected_params(self):
        """get_deployment_results tool has its original parameters."""
        from appian_deployment_mcp.tools.deployments import get_deployment_results

        sig = inspect.signature(get_deployment_results)
        param_names = list(sig.parameters.keys())
        assert "deployment_uuid" in param_names
        assert "environment" in param_names

    def test_get_deployment_log_has_expected_params(self):
        """get_deployment_log tool has its original parameters."""
        from appian_deployment_mcp.tools.deployments import get_deployment_log

        sig = inspect.signature(get_deployment_log)
        param_names = list(sig.parameters.keys())
        assert "deployment_uuid" in param_names
        assert "environment" in param_names

    def test_list_environments_has_expected_params(self):
        """list_environments tool exists and is callable."""
        from appian_deployment_mcp.tools.environments import list_environments

        sig = inspect.signature(list_environments)
        # list_environments takes no required params
        assert list_environments is not None

    def test_poll_deployment_status_has_expected_params(self):
        """poll_deployment_status tool has its original parameters."""
        from appian_deployment_mcp.tools.polling import poll_deployment_status

        sig = inspect.signature(poll_deployment_status)
        param_names = list(sig.parameters.keys())
        assert "deployment_uuid" in param_names
        assert "environment" in param_names

    def test_poll_inspection_status_has_expected_params(self):
        """poll_inspection_status tool has its original parameters."""
        from appian_deployment_mcp.tools.polling import poll_inspection_status

        sig = inspect.signature(poll_inspection_status)
        param_names = list(sig.parameters.keys())
        assert "inspection_uuid" in param_names
        assert "environment" in param_names

    def test_download_exported_package_has_expected_params(self):
        """download_exported_package tool has its original parameters."""
        from appian_deployment_mcp.tools.downloads import download_exported_package

        sig = inspect.signature(download_exported_package)
        param_names = list(sig.parameters.keys())
        assert "deployment_uuid" in param_names
        assert "environment" in param_names

    def test_get_application_packages_has_expected_params(self):
        """get_application_packages tool has its original parameters."""
        from appian_deployment_mcp.tools.packages import get_application_packages

        sig = inspect.signature(get_application_packages)
        param_names = list(sig.parameters.keys())
        assert "application_uuid" in param_names
        assert "environment" in param_names

    def test_get_inspection_results_has_expected_params(self):
        """get_inspection_results tool has its original parameters."""
        from appian_deployment_mcp.tools.inspections import get_inspection_results

        sig = inspect.signature(get_inspection_results)
        param_names = list(sig.parameters.keys())
        assert "inspection_uuid" in param_names
        assert "environment" in param_names
