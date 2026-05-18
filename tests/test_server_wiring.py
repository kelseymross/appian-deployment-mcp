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
}


def test_all_tools_registered():
    """Verify all 11 expected tools are registered with the MCP server."""
    registered = {tool.name for tool in mcp._tool_manager.list_tools()}
    assert registered == EXPECTED_TOOLS


def test_tool_count():
    """Verify exactly 11 tools are registered."""
    registered = mcp._tool_manager.list_tools()
    assert len(registered) == 11
