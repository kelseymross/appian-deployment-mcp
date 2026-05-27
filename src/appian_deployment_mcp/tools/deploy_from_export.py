"""MCP tool for end-to-end export-and-deploy workflow."""

import shutil
import tempfile
from pathlib import Path

from ..client import AppianClient
from ..config import resolve_environment
from ..server import get_environments, mcp

# Track temp directories for cleanup
_active_temp_dirs: list[str] = []


@mcp.tool()
async def export_and_deploy(
    uuids: list[str],
    export_type: str,
    source_environment: str,
    target_environment: str,
    deployment_name: str,
    customization_file_path: str | None = None,
    include_database_scripts: bool = True,
    include_plugins: bool = True,
    skip_inspect: bool = False,
    save_directory: str | None = None,
) -> dict:
    """Export a package or application from one environment and deploy it to another.

    This is an end-to-end workflow tool that handles the full promotion pipeline:
    1. Exports from the source environment
    2. Polls until export completes
    3. Downloads the package (and DB scripts/plugins if present)
    4. Optionally inspects on the target environment
    5. Deploys to the target environment (only if inspection passes or is skipped)

    IMPORTANT - Pre-Deployment Inspection:
        By default, this tool will inspect the package on the target environment
        before deploying. If the inspection finds errors, the tool will STOP and
        return the inspection results for user review. The user can then decide
        to deploy manually using deploy_package, or fix the issues first.
        Set skip_inspect=True only if the user explicitly requests skipping inspection.

    IMPORTANT - Sensitive File Handling:
        If a customization_file_path is provided, NEVER display or echo its contents.

    Args:
        uuids: List of UUIDs to export. For packages, only a single UUID. For applications, can be multiple.
        export_type: Either "package" or "application".
        source_environment: The environment to export from.
        target_environment: The environment to deploy to.
        deployment_name: Name for both the export and import deployments.
        customization_file_path: Optional path to a .properties ICF file for the target environment.
        include_database_scripts: Whether to include database scripts in the deployment. Defaults to True.
        include_plugins: Whether to include plugins in the deployment. Defaults to True.
        skip_inspect: If True, skips the inspection step. Defaults to False.
        save_directory: Optional directory to save downloaded artifacts. If not provided, uses a temporary directory that is automatically cleaned up after deployment.

    Returns:
        A dict with export_uuid, import_uuid, inspection results (if performed),
        and final deployment status. Returns partial results if any step fails.
    """
    import asyncio

    if export_type not in ("package", "application"):
        return {"error": True, "message": f"Invalid export_type '{export_type}'."}

    if export_type == "package" and len(uuids) > 1:
        return {"error": True, "message": "Package exports only support a single UUID."}

    # Use temp directory if no save_directory provided
    using_temp_dir = save_directory is None
    if using_temp_dir:
        temp_dir = tempfile.mkdtemp(prefix="appian-deploy-")
        save_dir = Path(temp_dir)
        _active_temp_dirs.append(temp_dir)
    else:
        save_dir = Path(save_directory)
        save_dir.mkdir(parents=True, exist_ok=True)

    environments = get_environments()
    result_summary: dict = {"steps_completed": []}

    try:
        # Step 1: Export
        source_config = resolve_environment(environments, source_environment)
        source_client = AppianClient(source_config)
        try:
            export_json = {
                "uuids": uuids,
                "exportType": export_type,
                "name": f"{deployment_name} - Export",
            }
            export_result = await source_client.post_multipart(
                "/deployments", json_part=export_json, files={}, headers={"Action-Type": "export"}
            )
            if export_result.get("error"):
                return {"error": True, "step": "export", "details": export_result}

            export_uuid = export_result["uuid"]
            result_summary["export_uuid"] = export_uuid
            result_summary["steps_completed"].append("export_started")

            # Step 2: Poll export
            export_status = await _poll_until_complete(source_client, f"/deployments/{export_uuid}")
            if export_status.get("error") or export_status.get("status") == "FAILED":
                return {"error": True, "step": "export_poll", "details": export_status, **result_summary}

            result_summary["steps_completed"].append("export_completed")
            result_summary["export_result"] = export_status

            # Step 3: Download package
            package_zip_url = export_status.get("packageZip")
            if not package_zip_url:
                return {"error": True, "step": "download", "message": "No package zip in export.", **result_summary}

            package_path = save_dir / f"{deployment_name.replace(' ', '-').lower()}.zip"
            await source_client.download_file(package_zip_url, package_path)
            result_summary["package_file"] = str(package_path)
            result_summary["steps_completed"].append("package_downloaded")

            # Download DB scripts if present and requested
            db_scripts_info = export_status.get("databaseScripts", [])
            db_scripts_dir = None
            if db_scripts_info and include_database_scripts:
                db_scripts_dir = save_dir / "db-scripts"
                db_scripts_dir.mkdir(parents=True, exist_ok=True)
                for script in db_scripts_info:
                    script_path = db_scripts_dir / script["fileName"]
                    await source_client.download_file(script["url"], script_path)
                result_summary["db_scripts_directory"] = str(db_scripts_dir)
                result_summary["steps_completed"].append("db_scripts_downloaded")

            # Download plugins if present and requested
            plugins_zip_url = export_status.get("pluginsZip")
            plugins_path = None
            if plugins_zip_url and include_plugins:
                plugins_path = save_dir / f"{deployment_name.replace(' ', '-').lower()}-plugins.zip"
                await source_client.download_file(plugins_zip_url, plugins_path)
                result_summary["plugins_file"] = str(plugins_path)
                result_summary["steps_completed"].append("plugins_downloaded")

        finally:
            await source_client.close()

        # Step 4: Inspect on target (unless skipped)
        target_config = resolve_environment(environments, target_environment)
        target_client = AppianClient(target_config)
        try:
            if not skip_inspect:
                inspect_files: dict[str, tuple] = {}
                inspect_json: dict = {}

                pkg_path_obj = Path(package_path)
                inspect_files["zipFile"] = (pkg_path_obj.name, pkg_path_obj.read_bytes(), "application/zip")
                inspect_json["packageFileName"] = pkg_path_obj.name

                if customization_file_path:
                    icf_path = Path(customization_file_path)
                    if icf_path.exists():
                        inspect_files["ICF"] = (icf_path.name, icf_path.read_bytes(), "application/octet-stream")
                        inspect_json["customizationFileName"] = icf_path.name

                inspect_result = await target_client.post_multipart(
                    "/inspections", json_part=inspect_json, files=inspect_files
                )
                if inspect_result.get("error"):
                    result_summary["inspection_error"] = inspect_result
                    return {"error": True, "step": "inspection_submit", **result_summary}
                else:
                    inspection_uuid = inspect_result["uuid"]
                    inspection_status = await _poll_until_complete(
                        target_client, f"/inspections/{inspection_uuid}"
                    )
                    result_summary["inspection_uuid"] = inspection_uuid
                    result_summary["inspection_result"] = inspection_status
                    result_summary["steps_completed"].append("inspection_completed")

                    # Check for inspection errors — stop and return results for user review
                    problems = inspection_status.get("summary", {}).get("problems", {})
                    total_errors = problems.get("totalErrors", 0)
                    if total_errors > 0:
                        result_summary["inspection_passed"] = False
                        result_summary["message"] = (
                            f"Inspection found {total_errors} error(s). "
                            "Review the inspection results and decide whether to proceed. "
                            "To deploy anyway, call deploy_package directly with the downloaded artifacts."
                        )
                        return result_summary
                    result_summary["inspection_passed"] = True

            # Step 5: Deploy to target
            import_files: dict[str, tuple] = {}
            import_json: dict = {"name": deployment_name}

            pkg_path_obj = Path(package_path)
            import_files["zipFile"] = (pkg_path_obj.name, pkg_path_obj.read_bytes(), "application/zip")
            import_json["packageFileName"] = pkg_path_obj.name

            if customization_file_path:
                icf_path = Path(customization_file_path)
                if icf_path.exists():
                    import_files["ICF"] = (icf_path.name, icf_path.read_bytes(), "application/octet-stream")
                    import_json["customizationFileName"] = icf_path.name

            if plugins_path and plugins_path.exists():
                import_files["plugins"] = (plugins_path.name, plugins_path.read_bytes(), "application/zip")
                import_json["pluginsFileName"] = plugins_path.name

            if db_scripts_info and include_database_scripts and db_scripts_dir:
                data_source = export_status.get("dataSource")
                if data_source:
                    import_json["dataSource"] = data_source
                    import_json["databaseScripts"] = [
                        {"fileName": s["fileName"], "orderId": s["orderId"]}
                        for s in db_scripts_info
                    ]
                    for script in db_scripts_info:
                        script_file = db_scripts_dir / script["fileName"]
                        if script_file.exists():
                            import_files[script["fileName"]] = (
                                script["fileName"],
                                script_file.read_bytes(),
                                "application/sql",
                            )

            deploy_result = await target_client.post_multipart(
                "/deployments",
                json_part=import_json,
                files=import_files,
                headers={"Action-Type": "import"},
            )
            if deploy_result.get("error"):
                return {"error": True, "step": "deploy", "details": deploy_result, **result_summary}

            import_uuid = deploy_result["uuid"]
            result_summary["import_uuid"] = import_uuid
            result_summary["steps_completed"].append("deploy_started")

            # Poll deployment
            deploy_status = await _poll_until_complete(target_client, f"/deployments/{import_uuid}")
            result_summary["deploy_result"] = deploy_status
            result_summary["steps_completed"].append("deploy_completed")
            result_summary["final_status"] = deploy_status.get("status", "UNKNOWN")

            return result_summary

        finally:
            await target_client.close()

    finally:
        # Auto-cleanup temp directory after workflow completes
        if using_temp_dir:
            try:
                shutil.rmtree(save_dir, ignore_errors=True)
                if temp_dir in _active_temp_dirs:
                    _active_temp_dirs.remove(temp_dir)
            except Exception:
                pass  # Best-effort cleanup


@mcp.tool()
async def cleanup_deployment_artifacts() -> dict:
    """Clean up any leftover temporary deployment artifacts from disk.

    This tool removes any temporary directories created by the export_and_deploy
    workflow that may not have been cleaned up (e.g., due to errors or interruptions).
    It does NOT remove files saved to user-specified directories.

    Returns:
        A dict with the number of directories cleaned and their paths.
    """
    cleaned = []
    remaining = []

    for temp_dir in list(_active_temp_dirs):
        try:
            if Path(temp_dir).exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
                cleaned.append(temp_dir)
            _active_temp_dirs.remove(temp_dir)
        except Exception:
            remaining.append(temp_dir)

    return {
        "cleaned_directories": cleaned,
        "total_cleaned": len(cleaned),
        "remaining": remaining,
    }


async def _poll_until_complete(
    client: AppianClient, path: str, max_wait: int = 300, interval: int = 5
) -> dict:
    """Poll an endpoint until it reaches a terminal status or times out."""
    import asyncio
    import time

    start = time.time()
    while True:
        result = await client.get(path)
        if result.get("error"):
            return result

        status = result.get("status", "")
        if status not in ("IN_PROGRESS",):
            return result

        elapsed = time.time() - start
        if elapsed >= max_wait:
            return {"error": True, "message": "Timed out waiting for completion.", "last_status": result}

        await asyncio.sleep(interval)
