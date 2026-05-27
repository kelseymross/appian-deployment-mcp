"""Tests verifying all tool modules are wired to the shared MCP server instance."""

from appian_deployment_mcp.server import mcp

EXPECTED_TOOLS = {
    "list_environments",
    "get_application_packages",
    "export_package",
    "inspect_package",
    "get_inspection_results",
    "deploy_package",
    "get_deployment_results",
    "get_deployment_log",
    "poll_deployment_status",
    "poll_inspection_status",
    "download_exported_package",
    "download_exported_database_scripts",
    "download_exported_plugins",
    "download_exported_customization_file",
    "export_and_deploy",
    "cleanup_deployment_artifacts",
    "approve_deployment",
    "reject_deployment",
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


def test_all_tools_registered():
    """Verify all expected tools are registered with the MCP server."""
    registered = {tool.name for tool in mcp._tool_manager.list_tools()}
    assert registered == EXPECTED_TOOLS


def test_tool_count():
    """Verify expected number of tools are registered."""
    registered = mcp._tool_manager.list_tools()
    assert len(registered) == 28
