"""MCP tools for downloading exported deployment resources."""

from pathlib import Path
from urllib.parse import urlparse

from ..client import AppianClient
from ..config import get_save_directory, resolve_environment
from ..server import get_environments, mcp


@mcp.tool()
async def download_exported_package(
    deployment_uuid: str,
    filename: str | None = None,
    save_directory: str | None = None,
    environment: str | None = None,
) -> dict:
    """Download the exported package .zip file from a completed export deployment.

    Note: Exports may also include Import Customization Files (ICF / .properties files)
    that contain sensitive environment-specific values. If downloading or handling ICF files:
    - NEVER display or echo the contents of .properties/ICF files in chat or responses.
    - Reference these files by path only.
    - Describe structure (e.g., "contains 3 constants") without revealing actual values.

    Args:
        deployment_uuid: The UUID of the export deployment to download.
        filename: Optional name for the downloaded file (e.g. "my-package.zip"). If not provided, uses the filename from the export URL.
        save_directory: Optional directory to save the file to. Defaults to APPIAN_SAVE_DIRECTORY env var, or system temp directory.
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

        # Determine filename
        if filename:
            save_filename = filename
        else:
            url_path = urlparse(package_zip_url).path
            save_filename = Path(url_path).name or f"{deployment_uuid}.zip"

        save_dir = Path(save_directory) if save_directory else Path(get_save_directory())
        save_path = save_dir / save_filename

        await client.download_file(package_zip_url, save_path)

        return {
            "file_path": str(save_path),
            "file_size_bytes": save_path.stat().st_size,
        }
    finally:
        await client.close()


@mcp.tool()
async def download_exported_database_scripts(
    deployment_uuid: str,
    save_directory: str | None = None,
    environment: str | None = None,
) -> dict:
    """Download all database script (.sql) files from a completed export deployment.

    Retrieves the export results to find database script URLs, then downloads
    each script file to the specified directory.

    Args:
        deployment_uuid: The UUID of the export deployment.
        save_directory: Optional directory to save the script files to. Defaults to a 'db-scripts' subdirectory under APPIAN_SAVE_DIRECTORY env var, or system temp directory.
        environment: Optional environment name. Uses the default environment if not specified.

    Returns:
        A dict with downloaded_files (list of file paths), total_files, and data_source on success, or an error dict.
    """
    config = resolve_environment(get_environments(), environment)
    client = AppianClient(config)
    try:
        result = await client.get(f"/deployments/{deployment_uuid}")

        if result.get("error"):
            return result

        db_scripts = result.get("databaseScripts")
        if not db_scripts:
            return {
                "error": True,
                "message": "Export does not contain database scripts, or the deployment is not a completed package export.",
            }

        save_dir = Path(save_directory) if save_directory else Path(get_save_directory()) / "db-scripts"
        save_dir.mkdir(parents=True, exist_ok=True)

        downloaded_files = []
        for script in db_scripts:
            script_url = script.get("url")
            script_filename = script.get("fileName")
            if not script_url or not script_filename:
                continue

            save_path = save_dir / script_filename
            await client.download_file(script_url, save_path)
            downloaded_files.append({
                "file_path": str(save_path),
                "file_name": script_filename,
                "order_id": script.get("orderId"),
                "file_size_bytes": save_path.stat().st_size,
            })

        return {
            "downloaded_files": downloaded_files,
            "total_files": len(downloaded_files),
            "data_source": result.get("dataSource"),
            "save_directory": str(save_dir),
        }
    finally:
        await client.close()


@mcp.tool()
async def download_exported_plugins(
    deployment_uuid: str,
    filename: str | None = None,
    save_directory: str | None = None,
    environment: str | None = None,
) -> dict:
    """Download the exported plugins .zip file from a completed export deployment.

    Args:
        deployment_uuid: The UUID of the export deployment.
        filename: Optional name for the downloaded file (e.g. "plugins.zip"). If not provided, defaults to "<deployment_uuid>-plugins.zip".
        save_directory: Optional directory to save the file to. Defaults to APPIAN_SAVE_DIRECTORY env var, or system temp directory.
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

        plugins_zip_url = result.get("pluginsZip")
        if not plugins_zip_url:
            return {
                "error": True,
                "message": "Export does not contain plugins, or the deployment is not a completed package export.",
            }

        save_filename = filename or f"{deployment_uuid}-plugins.zip"
        save_dir = Path(save_directory) if save_directory else Path(get_save_directory())
        save_path = save_dir / save_filename

        await client.download_file(plugins_zip_url, save_path)

        return {
            "file_path": str(save_path),
            "file_size_bytes": save_path.stat().st_size,
        }
    finally:
        await client.close()


@mcp.tool()
async def download_exported_customization_file(
    deployment_uuid: str,
    filename: str | None = None,
    save_directory: str | None = None,
    template: bool = False,
    environment: str | None = None,
) -> dict:
    """Download the Import Customization File (ICF) from a completed export deployment.

    Can download either the customization file (with current environment values) or
    the customization file template (blank, for filling in target environment values).

    IMPORTANT - Sensitive File Handling:
        ICF files contain sensitive environment-specific values such as API keys,
        connection strings, passwords, and other secrets.
        - NEVER display or echo the contents of the downloaded .properties file in chat.
        - Reference the file by path only.
        - If describing the file, mention its structure without revealing actual values.

    Args:
        deployment_uuid: The UUID of the export deployment.
        filename: Optional name for the downloaded file. If not provided, defaults to "<deployment_uuid>.properties" or "<deployment_uuid>-template.properties".
        save_directory: Optional directory to save the file to. Defaults to APPIAN_SAVE_DIRECTORY env var, or system temp directory.
        template: If True, downloads the blank template instead of the file with values. Defaults to False.
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

        if template:
            icf_url = result.get("customizationFileTemplate")
            error_msg = "Export does not contain a customization file template."
            default_suffix = "-template.properties"
        else:
            icf_url = result.get("customizationFile")
            if not icf_url:
                # Fall back to template if no values file exists
                icf_url = result.get("customizationFileTemplate")
                if icf_url:
                    default_suffix = "-template.properties"
                else:
                    return {
                        "error": True,
                        "message": "Export does not contain a customization file or template.",
                    }
            else:
                default_suffix = ".properties"
                error_msg = "Export does not contain a customization file."

        if not icf_url:
            return {"error": True, "message": error_msg}

        save_filename = filename or f"{deployment_uuid}{default_suffix}"
        save_dir = Path(save_directory) if save_directory else Path(get_save_directory())
        save_path = save_dir / save_filename

        await client.download_file(icf_url, save_path)

        return {
            "file_path": str(save_path),
            "file_size_bytes": save_path.stat().st_size,
            "is_template": template or (default_suffix == "-template.properties"),
        }
    finally:
        await client.close()
