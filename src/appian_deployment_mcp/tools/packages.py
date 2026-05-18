"""MCP tool for retrieving application package details."""

from ..client import AppianClient
from ..config import resolve_environment
from ..server import get_environments, mcp


@mcp.tool()
async def get_application_packages(
    application_uuid: str,
    environment: str | None = None,
) -> dict:
    """Retrieve the list of packages for an Appian application.

    Args:
        application_uuid: The UUID of the Appian application.
        environment: Optional environment name. Uses the default environment if not specified.

    Returns:
        The list of packages with uuid, name, description, objectCount,
        databaseScriptCount, pluginCount, and createdTimestamp for each package.
    """
    config = resolve_environment(get_environments(), environment)
    client = AppianClient(config)
    try:
        return await client.get(f"/applications/{application_uuid}/packages")
    finally:
        await client.close()
