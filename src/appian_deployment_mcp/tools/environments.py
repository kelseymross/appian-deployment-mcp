"""MCP tool for listing configured Appian environments."""

from ..server import get_environments, mcp


@mcp.tool()
def list_environments() -> list[str]:
    """Return the names of all configured Appian environments."""
    return sorted(get_environments().keys())
