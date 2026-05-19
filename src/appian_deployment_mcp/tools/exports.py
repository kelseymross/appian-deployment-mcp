"""MCP tool for exporting Appian packages."""

from ..client import AppianClient
from ..config import resolve_environment
from ..server import get_environments, mcp


@mcp.tool()
async def export_package(
    uuids: list[str],
    export_type: str,
    name: str | None = None,
    description: str | None = None,
    environment: str | None = None,
) -> dict:
    """Export an Appian package or application.

    Args:
        uuids: List of UUIDs to export.
        export_type: Either "package" or "application".
        name: Optional name for the export.
        description: Optional description for the export.
        environment: Optional environment name. Uses the default environment if not specified.

    Returns:
        The deployment UUID, URL, and status from the Appian API.
    """
    if export_type not in ("package", "application"):
        return {
            "error": True,
            "message": f"Invalid export_type '{export_type}'. Must be 'package' or 'application'.",
        }

    json_part: dict = {
        "uuids": uuids,
        "exportType": export_type,
    }
    if name is not None:
        json_part["name"] = name
    if description is not None:
        json_part["description"] = description

    config = resolve_environment(get_environments(), environment)
    client = AppianClient(config)
    try:
        return await client.post_multipart(
            "/deployments", json_part=json_part, files={}, headers={"Action-Type": "export"}
        )
    finally:
        await client.close()
