"""MCP tools for inspecting Appian packages."""

from pathlib import Path

from ..client import AppianClient
from ..config import resolve_environment
from ..server import get_environments, mcp


@mcp.tool()
async def inspect_package(
    package_file_path: str,
    customization_file_path: str | None = None,
    admin_console_settings_file_path: str | None = None,
    environment: str | None = None,
) -> dict:
    """Inspect an Appian package for potential deployment issues.

    Args:
        package_file_path: Path to the package .zip file.
        customization_file_path: Optional path to the .properties ICF file.
        admin_console_settings_file_path: Optional path to the admin console settings .zip.
        environment: Optional environment name. Uses the default environment if not specified.

    Returns:
        The inspection UUID and URL from the Appian API.
    """
    # Validate all file paths exist
    paths_to_check: list[tuple[str, str]] = [
        (package_file_path, "package_file_path"),
    ]
    if customization_file_path is not None:
        paths_to_check.append((customization_file_path, "customization_file_path"))
    if admin_console_settings_file_path is not None:
        paths_to_check.append(
            (admin_console_settings_file_path, "admin_console_settings_file_path")
        )

    for file_path, _param_name in paths_to_check:
        p = Path(file_path)
        if not p.exists():
            return {"error": True, "message": f"File not found: {file_path}"}

    # Build multipart files dict
    package_path = Path(package_file_path)
    files: dict[str, tuple] = {
        "zipFile": (package_path.name, package_path.read_bytes(), "application/zip"),
    }

    if customization_file_path is not None:
        icf_path = Path(customization_file_path)
        files["ICF"] = (
            icf_path.name,
            icf_path.read_bytes(),
            "application/octet-stream",
        )

    if admin_console_settings_file_path is not None:
        acs_path = Path(admin_console_settings_file_path)
        files["adminConsoleSettings"] = (
            acs_path.name,
            acs_path.read_bytes(),
            "application/zip",
        )

    json_part: dict = {
        "packageFileName": package_path.name,
    }
    if customization_file_path is not None:
        json_part["customizationFileName"] = Path(customization_file_path).name
    if admin_console_settings_file_path is not None:
        json_part["adminConsoleSettingsFileName"] = Path(admin_console_settings_file_path).name

    config = resolve_environment(get_environments(), environment)
    client = AppianClient(config)
    try:
        return await client.post_multipart("/inspections", json_part=json_part, files=files)
    finally:
        await client.close()


@mcp.tool()
async def get_inspection_results(
    inspection_uuid: str,
    environment: str | None = None,
) -> dict:
    """Retrieve the results of a package inspection.

    Args:
        inspection_uuid: The UUID of the inspection to retrieve results for.
        environment: Optional environment name. Uses the default environment if not specified.

    Returns:
        The inspection results including status, object counts, errors, and warnings
        when completed, or just the status when still in progress.
    """
    config = resolve_environment(get_environments(), environment)
    client = AppianClient(config)
    try:
        return await client.get(f"/inspections/{inspection_uuid}")
    finally:
        await client.close()
