"""Pipeline execution engine for multi-environment deployments."""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import httpx

from ..client import AppianClient
from ..config import EnvironmentConfig
from .models import (
    PipelineRun,
    PipelineStage,
    PipelineStatus,
    StageOperation,
    StageResult,
    StageStatus,
)
from .store import PipelineStore

logger = logging.getLogger(__name__)

DEPLOYMENT_TERMINAL_STATUSES = {
    "COMPLETED",
    "COMPLETED_WITH_ERRORS",
    "COMPLETED_WITH_IMPORT_ERRORS",
    "COMPLETED_WITH_PUBLISH_ERRORS",
    "COMPLETED_WITH_EXPORT_ERRORS",
    "FAILED",
    "REJECTED",
}

DEPLOYMENT_FAILURE_STATUSES = {
    "FAILED",
    "COMPLETED_WITH_ERRORS",
    "COMPLETED_WITH_IMPORT_ERRORS",
    "COMPLETED_WITH_PUBLISH_ERRORS",
    "COMPLETED_WITH_EXPORT_ERRORS",
    "REJECTED",
}

INSPECTION_TERMINAL_STATUSES = {"COMPLETED", "FAILED"}

POLL_INTERVAL_SECONDS = 5
MAX_POLL_SECONDS = 600
MAX_REVIEW_POLL_SECONDS = 3600  # Wait up to 1 hour for review approval


class PipelineEngine:
    """Orchestrates pipeline execution across environments."""

    def __init__(
        self,
        environments: dict[str, EnvironmentConfig],
        store: PipelineStore,
    ) -> None:
        self._environments = environments
        self._store = store

    async def execute(self, run_id: str) -> None:
        """Execute a pipeline run to completion. Runs as a background task.

        Updates the PipelineStore as stages progress. Suspends at approval
        gates until signaled. Respects cancellation via the run's cancel event.
        """
        run = self._store.get_run(run_id)
        if run is None:
            return

        run.status = PipelineStatus.IN_PROGRESS
        temp_dir = Path(tempfile.mkdtemp(prefix="pipeline_"))

        try:
            # First stage is always the export source
            source_stage = run.stages[0]

            if await self._check_cancelled(run):
                return

            # Execute export on the first stage
            package_path = await self._execute_export(run, source_stage, temp_dir)
            if package_path is None:
                # Export failed — run is already marked FAILED
                return

            if await self._check_cancelled(run):
                return

            # For each subsequent stage: optionally inspect, optionally approve, import
            for stage in run.stages[1:]:
                if await self._check_cancelled(run):
                    return

                # Optionally inspect before deploy
                if run.config.inspect_before_deploy:
                    inspect_ok = await self._execute_inspect(run, stage, package_path)
                    if not inspect_ok:
                        return

                    if await self._check_cancelled(run):
                        return

                # Optionally wait for approval
                if stage.environment in run.config.approval_environments:
                    approved = await self._wait_for_approval(run)
                    if not approved:
                        # Cancelled or rejected
                        if not run._cancel_event.is_set():
                            # Rejected — mark as cancelled
                            run.status = PipelineStatus.CANCELLED
                            for s in run.stages:
                                if s.status == StageStatus.PENDING:
                                    s.status = StageStatus.SKIPPED
                        else:
                            await self._check_cancelled(run)
                        return

                    if await self._check_cancelled(run):
                        return

                    # Reset approval state for the next gate
                    run._approval_event = asyncio.Event()
                    run._approval_granted = False

                    # Reset status back to IN_PROGRESS after approval
                    run.status = PipelineStatus.IN_PROGRESS

                # Execute import
                import_ok = await self._execute_import(run, stage, package_path)
                if not import_ok:
                    return

                if await self._check_cancelled(run):
                    return

            # All stages completed successfully
            run.status = PipelineStatus.COMPLETED
            run.completed_at = datetime.utcnow()

        finally:
            # Clean up temp directory
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
            except OSError:
                logger.warning("Failed to clean up temp directory: %s", temp_dir)

    async def _execute_export(
        self,
        run: PipelineRun,
        stage: PipelineStage,
        temp_dir: Path,
    ) -> Path | None:
        """Export package from source environment, poll to completion, download artifact.

        Returns the path to the downloaded package, or None if export failed.
        """
        stage.status = StageStatus.EXPORTING
        stage.operation = StageOperation.EXPORT
        stage.started_at = datetime.utcnow()

        env_config = self._environments[stage.environment]
        client = AppianClient(env_config)

        try:
            # POST export
            json_part = {
                "uuids": run.config.uuids,
                "exportType": run.config.export_type,
                "name": run.config.export_name,
            }

            result = await client.post_multipart(
                "/deployments",
                json_part=json_part,
                files={},
                headers={"Action-Type": "export"},
            )

            if result.get("error"):
                stage.status = StageStatus.FAILED
                stage.completed_at = datetime.utcnow()
                stage.result = StageResult(
                    environment=stage.environment,
                    operation=StageOperation.EXPORT,
                    status="FAILED",
                    error_type="api_error",
                    error_domain=env_config.domain,
                )
                run.status = PipelineStatus.FAILED
                run.completed_at = datetime.utcnow()
                return None

            deployment_uuid = result.get("uuid")

            # Poll until terminal
            poll_result = await self._poll_deployment(client, deployment_uuid, run)
            if poll_result is None:
                # Cancelled during polling
                return None

            status = poll_result.get("status", "")

            if status != "COMPLETED":
                # Export failed
                stage.status = StageStatus.FAILED
                stage.completed_at = datetime.utcnow()
                stage.result = StageResult(
                    environment=stage.environment,
                    operation=StageOperation.EXPORT,
                    deployment_uuid=deployment_uuid,
                    status=status,
                    deployment_log_url=poll_result.get("deploymentLogUrl"),
                )
                run.status = PipelineStatus.FAILED
                run.completed_at = datetime.utcnow()
                return None

            # Download the package artifact
            package_zip_url = poll_result.get("packageZip")
            if not package_zip_url:
                stage.status = StageStatus.FAILED
                stage.completed_at = datetime.utcnow()
                stage.result = StageResult(
                    environment=stage.environment,
                    operation=StageOperation.EXPORT,
                    deployment_uuid=deployment_uuid,
                    status=status,
                    error_type="missing_package_url",
                )
                run.status = PipelineStatus.FAILED
                run.completed_at = datetime.utcnow()
                return None

            package_path = temp_dir / f"{deployment_uuid}.zip"
            await client.download_file(package_zip_url, package_path)

            # Mark stage completed
            stage.status = StageStatus.COMPLETED
            stage.completed_at = datetime.utcnow()
            stage.result = StageResult(
                environment=stage.environment,
                operation=StageOperation.EXPORT,
                deployment_uuid=deployment_uuid,
                status=status,
                package_path=str(package_path),
                deployment_log_url=poll_result.get("deploymentLogUrl"),
            )
            return package_path

        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            stage.status = StageStatus.FAILED
            stage.completed_at = datetime.utcnow()
            error_type = "timeout" if isinstance(exc, httpx.TimeoutException) else "network_error"
            stage.result = StageResult(
                environment=stage.environment,
                operation=StageOperation.EXPORT,
                error_type=error_type,
                error_domain=env_config.domain,
            )
            run.status = PipelineStatus.FAILED
            run.completed_at = datetime.utcnow()
            return None
        finally:
            await client.close()

    async def _execute_inspect(
        self,
        run: PipelineRun,
        stage: PipelineStage,
        package_path: Path,
    ) -> bool:
        """Inspect package on target environment, poll to completion.

        Returns True if inspection passed, False if failed.
        """
        stage.status = StageStatus.INSPECTING
        stage.operation = StageOperation.INSPECT
        if stage.started_at is None:
            stage.started_at = datetime.utcnow()

        env_config = self._environments[stage.environment]
        client = AppianClient(env_config)

        try:
            # POST inspection with package file
            json_part = {
                "packageFileName": package_path.name,
            }
            files = {
                "zipFile": (
                    package_path.name,
                    package_path.read_bytes(),
                    "application/zip",
                ),
            }

            result = await client.post_multipart(
                "/inspections",
                json_part=json_part,
                files=files,
            )

            if result.get("error"):
                stage.status = StageStatus.FAILED
                stage.completed_at = datetime.utcnow()
                stage.result = StageResult(
                    environment=stage.environment,
                    operation=StageOperation.INSPECT,
                    status="FAILED",
                    error_type="api_error",
                    error_domain=env_config.domain,
                )
                run.status = PipelineStatus.FAILED
                run.completed_at = datetime.utcnow()
                return False

            inspection_uuid = result.get("uuid")

            # Poll until terminal
            poll_result = await self._poll_inspection(client, inspection_uuid, run)
            if poll_result is None:
                # Cancelled during polling
                return False

            status = poll_result.get("status", "")

            if status != "COMPLETED":
                # Inspection failed
                stage.status = StageStatus.FAILED
                stage.completed_at = datetime.utcnow()
                stage.result = StageResult(
                    environment=stage.environment,
                    operation=StageOperation.INSPECT,
                    deployment_uuid=inspection_uuid,
                    status=status,
                    errors=poll_result.get("errors"),
                    warnings=poll_result.get("warnings"),
                    object_counts=poll_result.get("objectCounts"),
                )
                run.status = PipelineStatus.FAILED
                run.completed_at = datetime.utcnow()
                return False

            # Inspection passed — store result but don't mark stage completed yet
            # (import still needs to happen)
            stage.result = StageResult(
                environment=stage.environment,
                operation=StageOperation.INSPECT,
                deployment_uuid=inspection_uuid,
                status=status,
                errors=poll_result.get("errors"),
                warnings=poll_result.get("warnings"),
                object_counts=poll_result.get("objectCounts"),
            )
            return True

        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            stage.status = StageStatus.FAILED
            stage.completed_at = datetime.utcnow()
            error_type = "timeout" if isinstance(exc, httpx.TimeoutException) else "network_error"
            stage.result = StageResult(
                environment=stage.environment,
                operation=StageOperation.INSPECT,
                error_type=error_type,
                error_domain=env_config.domain,
            )
            run.status = PipelineStatus.FAILED
            run.completed_at = datetime.utcnow()
            return False
        finally:
            await client.close()

    async def _execute_import(
        self,
        run: PipelineRun,
        stage: PipelineStage,
        package_path: Path,
    ) -> bool:
        """Import package to target environment, poll to completion.

        Returns True if import succeeded, False if failed.
        """
        stage.status = StageStatus.DEPLOYING
        stage.operation = StageOperation.IMPORT
        if stage.started_at is None:
            stage.started_at = datetime.utcnow()

        env_config = self._environments[stage.environment]
        client = AppianClient(env_config)

        try:
            # Build deploy name from template if provided
            deploy_name = run.config.export_name
            if run.config.deploy_name_template:
                deploy_name = run.config.deploy_name_template.replace(
                    "{environment}", stage.environment
                ).replace("{stage_number}", str(stage.stage_number))

            # Build multipart request
            json_part: dict = {
                "name": deploy_name,
                "packageFileName": package_path.name,
            }

            files: dict[str, tuple] = {
                "zipFile": (
                    package_path.name,
                    package_path.read_bytes(),
                    "application/zip",
                ),
            }

            # Add ICF if configured
            if run.config.customization_file_path:
                icf_path = Path(run.config.customization_file_path)
                if icf_path.exists():
                    json_part["customizationFileName"] = icf_path.name
                    files["ICF"] = (
                        icf_path.name,
                        icf_path.read_bytes(),
                        "application/octet-stream",
                    )

            result = await client.post_multipart(
                "/deployments",
                json_part=json_part,
                files=files,
                headers={"Action-Type": "import"},
            )

            if result.get("error"):
                stage.status = StageStatus.FAILED
                stage.completed_at = datetime.utcnow()
                stage.result = StageResult(
                    environment=stage.environment,
                    operation=StageOperation.IMPORT,
                    status="FAILED",
                    error_type="api_error",
                    error_domain=env_config.domain,
                )
                run.status = PipelineStatus.FAILED
                run.completed_at = datetime.utcnow()
                return False

            deployment_uuid = result.get("uuid")

            # Poll until terminal
            poll_result = await self._poll_deployment(client, deployment_uuid, run)
            if poll_result is None:
                # Cancelled during polling
                return False

            status = poll_result.get("status", "")

            if status != "COMPLETED":
                # Import failed
                stage.status = StageStatus.FAILED
                stage.completed_at = datetime.utcnow()
                stage.result = StageResult(
                    environment=stage.environment,
                    operation=StageOperation.IMPORT,
                    deployment_uuid=deployment_uuid,
                    status=status,
                    deployment_log_url=poll_result.get("deploymentLogUrl"),
                    object_counts=poll_result.get("objectCounts"),
                )
                run.status = PipelineStatus.FAILED
                run.completed_at = datetime.utcnow()
                return False

            # Import succeeded
            stage.status = StageStatus.COMPLETED
            stage.completed_at = datetime.utcnow()
            stage.result = StageResult(
                environment=stage.environment,
                operation=StageOperation.IMPORT,
                deployment_uuid=deployment_uuid,
                status=status,
                deployment_log_url=poll_result.get("deploymentLogUrl"),
                object_counts=poll_result.get("objectCounts"),
            )
            return True

        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            stage.status = StageStatus.FAILED
            stage.completed_at = datetime.utcnow()
            error_type = "timeout" if isinstance(exc, httpx.TimeoutException) else "network_error"
            stage.result = StageResult(
                environment=stage.environment,
                operation=StageOperation.IMPORT,
                error_type=error_type,
                error_domain=env_config.domain,
            )
            run.status = PipelineStatus.FAILED
            run.completed_at = datetime.utcnow()
            return False
        finally:
            await client.close()

    async def _check_cancelled(self, run: PipelineRun) -> bool:
        """Check cancel event, mark CANCELLED + skip pending stages if set.

        Returns True if the run was cancelled.
        """
        if run._cancel_event.is_set():
            run.status = PipelineStatus.CANCELLED
            run.completed_at = datetime.utcnow()
            for stage in run.stages:
                if stage.status == StageStatus.PENDING:
                    stage.status = StageStatus.SKIPPED
            return True
        return False

    async def _wait_for_approval(self, run: PipelineRun) -> bool:
        """Wait for approval or cancellation. Returns True if approved."""
        run.status = PipelineStatus.AWAITING_APPROVAL

        # Wait for either approval or cancellation
        approval_task = asyncio.create_task(run._approval_event.wait())
        cancel_task = asyncio.create_task(run._cancel_event.wait())

        done, pending = await asyncio.wait(
            [approval_task, cancel_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        if run._cancel_event.is_set():
            return False  # Cancelled

        return run._approval_granted  # True if approved, False if rejected

    async def _poll_deployment(
        self,
        client: AppianClient,
        deployment_uuid: str,
        run: PipelineRun,
    ) -> dict | None:
        """Poll deployment until terminal status. Returns result or None if cancelled.

        If the deployment enters PENDING_REVIEW, extends the polling timeout to
        allow time for manual approval. The pipeline can still be cancelled during this wait.
        """
        elapsed = 0.0
        in_review = False
        max_seconds = MAX_POLL_SECONDS

        while elapsed < max_seconds:
            if run._cancel_event.is_set():
                await self._check_cancelled(run)
                return None

            result = await client.get(f"/deployments/{deployment_uuid}")

            if result.get("error"):
                return result

            status = result.get("status", "")

            # If we detect PENDING_REVIEW, extend timeout and update stage status
            if status == "PENDING_REVIEW" and not in_review:
                in_review = True
                max_seconds = MAX_REVIEW_POLL_SECONDS
                logger.info(
                    "Deployment %s is pending review. Waiting for approval (cancel pipeline to abort).",
                    deployment_uuid,
                )

            if status in DEPLOYMENT_TERMINAL_STATUSES:
                return result

            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            elapsed += POLL_INTERVAL_SECONDS

        # Timed out — treat as failure
        return {"status": "FAILED", "error": True, "message": "Polling timed out"}

    async def _poll_inspection(
        self,
        client: AppianClient,
        inspection_uuid: str,
        run: PipelineRun,
    ) -> dict | None:
        """Poll inspection until terminal status. Returns result or None if cancelled."""
        elapsed = 0.0
        while elapsed < MAX_POLL_SECONDS:
            if run._cancel_event.is_set():
                await self._check_cancelled(run)
                return None

            result = await client.get(f"/inspections/{inspection_uuid}")

            if result.get("error"):
                return result

            status = result.get("status", "")
            if status in INSPECTION_TERMINAL_STATUSES:
                return result

            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            elapsed += POLL_INTERVAL_SECONDS

        # Timed out — treat as failure
        return {"status": "FAILED", "error": True, "message": "Polling timed out"}
