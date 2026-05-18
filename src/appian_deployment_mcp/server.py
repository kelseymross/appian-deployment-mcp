"""MCP server entry point using FastMCP with stdio transport."""

from mcp.server.fastmcp import FastMCP

from .config import EnvironmentConfig, load_environments

mcp = FastMCP(
    name="appian-deployment",
    instructions="Appian Deployment REST API v2 — export, inspect, deploy, and monitor Appian packages.",
)

_environments: dict[str, EnvironmentConfig] = {}


def get_environments() -> dict[str, EnvironmentConfig]:
    """Return the loaded environment configurations."""
    return _environments


# Import tool modules so their @mcp.tool() decorators register against this mcp instance.
# These imports MUST come after mcp and get_environments are defined to avoid circular imports.
from .tools import (  # noqa: E402, F401
    deployments,
    downloads,
    environments,
    exports,
    inspections,
    packages,
    polling,
)


def main():
    """Run the MCP server with stdio transport."""
    global _environments
    _environments = load_environments()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
