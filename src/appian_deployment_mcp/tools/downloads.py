"""MCP tool for downloading exported packages."""

import os
from pathlib import Path
from urllib.parse import urlparse

from ..client import AppianClient
from ..config import resolve_environment
from ..server import get_environments, mcp


@mcp.tool()
async def download_exported_package(
    deployment_uuid: str,
    save_directory: str | None = None,
    environment: str | None = None,
) -> dict:
    """Download the exported package .zip file from a completed export deployment.

    Args:
        deployment_uuid: The UUID of the export deployment to download.
        save_directory: Optional directory to save the file to. Defaults to the current working directory.
        environment: Optional environment name. Uses the default environment if not specified.

    Returns:
        A dict with file_path and file_size_bytes on success, or an error dict.
    """
    config = resolve_environment(get_environments(), environment)
    client = AppianClient(config)
    try:
        result = await client.get(f"/deployments/{deployment_uuid}")

        if result.get("error"):
            return result

        package_zip_url = result.get("packageZip")
        if not package_zip_url:
            return {
                "error": True,
                "message": "Deployment is not a completed export or the UUID is invalid.",
            }

        # Extract filename from the URL path
        url_path = urlparse(package_zip_url).path
        filename = Path(url_path).name or f"{deployment_uuid}.zip"

        save_dir = Path(save_directory) if save_directory else Path(os.getcwd())
        save_path = save_dir / filename

        await client.download_file(package_zip_url, save_path)

        return {
            "file_path": str(save_path),
            "file_size_bytes": save_path.stat().st_size,
        }
    finally:
        await client.close()
