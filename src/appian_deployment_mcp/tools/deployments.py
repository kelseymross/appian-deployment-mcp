"""MCP tools for deploying packages and retrieving deployment results."""

from pathlib import Path

from ..client import AppianClient
from ..config import resolve_environment
from ..server import get_environments, mcp


@mcp.tool()
async def deploy_package(
    name: str,
    package_file_path: str | None = None,
    customization_file_path: str | None = None,
    admin_console_settings_file_path: str | None = None,
    plugins_file_path: str | None = None,
    data_source: str | None = None,
    database_scripts: list[dict] | None = None,
    database_scripts_folder: str | None = None,
    description: str | None = None,
    environment: str | None = None,
) -> dict:
    """Deploy (import) a package to an Appian environment.

    Args:
        name: Name for the deployment.
        package_file_path: Optional path to the package .zip file.
        customization_file_path: Optional path to the .properties ICF file.
        admin_console_settings_file_path: Optional path to the admin console settings .zip.
        plugins_file_path: Optional path to the plugins .zip file.
        data_source: Optional data source name or UUID for database scripts.
        database_scripts: Optional list of objects with fileName and orderId.
        database_scripts_folder: Optional path to folder containing the .sql files referenced in database_scripts.
        description: Optional description for the deployment.
        environment: Optional environment name. Uses the default environment if not specified.

    Returns:
        The deployment UUID, URL, and status from the Appian API.
    """
    # Validate at least one deployable artifact is provided
    has_data_source_scripts = data_source is not None and database_scripts is not None
    if not any([
        package_file_path,
        admin_console_settings_file_path,
        plugins_file_path,
        has_data_source_scripts,
    ]):
        return {
            "error": True,
            "message": "At least one deployable artifact is required: "
            "package_file_path, admin_console_settings_file_path, "
            "plugins_file_path, or data_source with database_scripts.",
        }

    # Validate all provided file paths exist
    paths_to_check: list[tuple[str, str]] = []
    if package_file_path is not None:
        paths_to_check.append((package_file_path, "package_file_path"))
    if customization_file_path is not None:
        paths_to_check.append((customization_file_path, "customization_file_path"))
    if admin_console_settings_file_path is not None:
        paths_to_check.append(
            (admin_console_settings_file_path, "admin_console_settings_file_path")
        )
    if plugins_file_path is not None:
        paths_to_check.append((plugins_file_path, "plugins_file_path"))

    for file_path, _param_name in paths_to_check:
        p = Path(file_path)
        if not p.exists():
            return {"error": True, "message": f"File not found: {file_path}"}

    # Build multipart files dict
    files: dict[str, tuple] = {}

    if package_file_path is not None:
        pkg_path = Path(package_file_path)
        files["zipFile"] = (pkg_path.name, pkg_path.read_bytes(), "application/zip")

    if customization_file_path is not None:
        icf_path = Path(customization_file_path)
        files["ICF"] = (icf_path.name, icf_path.read_bytes(), "application/octet-stream")

    if admin_console_settings_file_path is not None:
        acs_path = Path(admin_console_settings_file_path)
        files["adminConsoleSettings"] = (
            acs_path.name,
            acs_path.read_bytes(),
            "application/zip",
        )

    if plugins_file_path is not None:
        plug_path = Path(plugins_file_path)
        files["plugins"] = (plug_path.name, plug_path.read_bytes(), "application/zip")

    # Build JSON metadata part
    json_part: dict = {"name": name}
    if description is not None:
        json_part["description"] = description
    if package_file_path is not None:
        json_part["packageFileName"] = Path(package_file_path).name
    if customization_file_path is not None:
        json_part["customizationFileName"] = Path(customization_file_path).name
    if plugins_file_path is not None:
        json_part["pluginsFileName"] = Path(plugins_file_path).name
    if admin_console_settings_file_path is not None:
        json_part["adminConsoleSettingsFileName"] = Path(admin_console_settings_file_path).name
    if data_source is not None:
        json_part["dataSource"] = data_source
    if database_scripts is not None:
        json_part["databaseScripts"] = database_scripts

    # Upload database script files if folder is provided
    if database_scripts is not None and database_scripts_folder is not None:
        scripts_dir = Path(database_scripts_folder)
        if not scripts_dir.exists():
            return {"error": True, "message": f"Database scripts folder not found: {database_scripts_folder}"}
        for script in database_scripts:
            script_file = scripts_dir / script["fileName"]
            if not script_file.exists():
                return {"error": True, "message": f"Database script file not found: {script_file}"}
            files[script["fileName"]] = (script["fileName"], script_file.read_bytes(), "application/sql")

    config = resolve_environment(get_environments(), environment)
    client = AppianClient(config)
    try:
        return await client.post_multipart(
            "/deployments",
            json_part=json_part,
            files=files,
            headers={"Action-Type": "import"},
        )
    finally:
        await client.close()


@mcp.tool()
async def get_deployment_log(
    deployment_uuid: str,
    environment: str | None = None,
) -> str | dict:
    """Retrieve the deployment log for a deployment.

    Args:
        deployment_uuid: The UUID of the deployment to retrieve the log for.
        environment: Optional environment name. Uses the default environment if not specified.

    Returns:
        The plain text deployment log content, or an error dict if the API returns an error.
    """
    config = resolve_environment(get_environments(), environment)
    client = AppianClient(config)
    try:
        return await client.get_text(f"/deployments/{deployment_uuid}/log")
    finally:
        await client.close()


@mcp.tool()
async def get_deployment_results(
    deployment_uuid: str,
    environment: str | None = None,
) -> dict:
    """Retrieve the status and results of a deployment (import or export).

    Args:
        deployment_uuid: The UUID of the deployment to retrieve results for.
        environment: Optional environment name. Uses the default environment if not specified.

    Returns:
        The deployment results. For completed imports: status, object/plugin/admin counts,
        and deployment log URL. For completed exports: status, package zip URL, data source,
        database scripts, and deployment log URL. For in-progress operations: the current status.
    """
    config = resolve_environment(get_environments(), environment)
    client = AppianClient(config)
    try:
        return await client.get(f"/deployments/{deployment_uuid}")
    finally:
        await client.close()
