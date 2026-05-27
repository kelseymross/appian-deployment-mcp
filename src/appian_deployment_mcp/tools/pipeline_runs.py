"""MCP tools for executing and managing pipeline runs."""

from __future__ import annotations

import asyncio

from ..pipeline.models import (
    PipelineStatus,
    RunConfig,
    StageStatus,
)
from ..pipeline.validation import validate_pipeline_stages, validate_run_params
from ..server import get_environments, get_pipeline_engine, get_pipeline_store, mcp

# Terminal statuses that cannot be cancelled
_TERMINAL_STATUSES = {
    PipelineStatus.COMPLETED,
    PipelineStatus.FAILED,
    PipelineStatus.CANCELLED,
}


def _serialize_stage(stage) -> dict:
    """Serialize a PipelineStage to a dict for API responses."""
    result: dict = {
        "environment": stage.environment,
        "stage_number": stage.stage_number,
        "status": stage.status.value,
        "operation": stage.operation.value if stage.operation else None,
        "started_at": stage.started_at.isoformat() if stage.started_at else None,
        "completed_at": stage.completed_at.isoformat() if stage.completed_at else None,
    }
    if stage.result is not None:
        result["result"] = _serialize_stage_result(stage.result)
    return result


def _serialize_stage_result(sr) -> dict:
    """Serialize a StageResult to a dict for API responses."""
    return {
        "environment": sr.environment,
        "operation": sr.operation.value,
        "deployment_uuid": sr.deployment_uuid,
        "status": sr.status,
        "package_path": sr.package_path,
        "deployment_log_url": sr.deployment_log_url,
        "errors": sr.errors,
        "warnings": sr.warnings,
        "object_counts": sr.object_counts,
        "error_type": sr.error_type,
        "error_domain": sr.error_domain,
    }


def _serialize_run(run) -> dict:
    """Serialize a PipelineRun to a full status dict."""
    response = {
        "run_id": run.run_id,
        "pipeline_name": run.pipeline_name,
        "status": run.status.value,
        "stages": [_serialize_stage(s) for s in run.stages],
        "config": {
            "uuids": run.config.uuids,
            "export_type": run.config.export_type,
            "export_name": run.config.export_name,
            "deploy_name_template": run.config.deploy_name_template,
            "customization_file_path": run.config.customization_file_path,
            "inspect_before_deploy": run.config.inspect_before_deploy,
            "approval_environments": run.config.approval_environments,
        },
        "created_at": run.created_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "cancellation_reason": run.cancellation_reason,
        "rejection_reason": run.rejection_reason,
        "approval_comment": run.approval_comment,
    }

    # Req 4.4: When AWAITING_APPROVAL, include the pending environment and
    # inspection summary so the caller doesn't have to dig through stages.
    if run.status == PipelineStatus.AWAITING_APPROVAL:
        pending_env = None
        inspection_summary = None
        for stage in run.stages:
            if stage.status == StageStatus.PENDING and stage.result is not None:
                # This is the stage awaiting approval — it has an inspection result
                pending_env = stage.environment
                inspection_summary = {
                    "environment": stage.result.environment,
                    "errors": stage.result.errors or [],
                    "warnings": stage.result.warnings or [],
                    "total_errors": len(stage.result.errors) if stage.result.errors else 0,
                    "total_warnings": len(stage.result.warnings) if stage.result.warnings else 0,
                    "object_counts": stage.result.object_counts,
                }
                break
        response["pending_approval_environment"] = pending_env
        response["inspection_summary"] = inspection_summary

    return response


@mcp.tool()
async def run_pipeline(
    pipeline_name: str,
    uuids: list[str],
    export_type: str,
    export_name: str,
    deploy_name: str | None = None,
    customization_file_path: str | None = None,
    inspect_before_deploy: bool = True,
    approval_environments: list[str] | None = None,
) -> dict:
    """Execute a named pipeline to promote a package through all environments in sequence.

    Exports the package from the first environment, then sequentially deploys
    to each subsequent environment with optional inspection and approval gates.

    Args:
        pipeline_name: Name of an existing pipeline definition (max 128 chars).
        uuids: List of UUIDs to export (1-100 entries).
        export_type: Either "package" or "application".
        export_name: Name for the export deployment (max 256 chars).
        deploy_name: Optional template for import deployment names.
            Supports {environment} and {stage_number} placeholders.
        customization_file_path: Optional path to .properties ICF file.
        inspect_before_deploy: Whether to inspect before each import (default true).
        approval_environments: Optional list of environment names requiring approval.

    Returns:
        Dict with run_id and initial status, or an error dict if validation fails.
    """
    store = get_pipeline_store()

    # Validate pipeline exists
    definition = store.get_definition(pipeline_name)
    if definition is None:
        available = [d.name for d in store.list_definitions()]
        return {
            "error": f"Pipeline '{pipeline_name}' not found. "
            f"Available pipelines: {available}"
        }

    # Validate run parameters
    approval_envs = approval_environments or []
    validation_error = validate_run_params(
        uuids=uuids,
        export_type=export_type,
        stages=definition.stages,
        approval_environments=approval_envs,
        min_stages=1,
    )
    if validation_error is not None:
        return validation_error

    # Create run config
    config = RunConfig(
        uuids=uuids,
        export_type=export_type,
        export_name=export_name,
        deploy_name_template=deploy_name,
        customization_file_path=customization_file_path,
        inspect_before_deploy=inspect_before_deploy,
        approval_environments=approval_envs,
    )

    # Create the run
    run = store.create_run(
        definition_name=pipeline_name,
        config=config,
        stages=definition.stages,
    )

    # Launch engine execution as a background task
    engine = get_pipeline_engine()
    asyncio.create_task(engine.execute(run.run_id))

    return {
        "run_id": run.run_id,
        "pipeline_name": run.pipeline_name,
        "status": run.status.value,
    }


@mcp.tool()
async def run_adhoc_pipeline(
    stages: list[str],
    uuids: list[str],
    export_type: str,
    export_name: str,
    deploy_name: str | None = None,
    customization_file_path: str | None = None,
    inspect_before_deploy: bool = True,
    approval_environments: list[str] | None = None,
) -> dict:
    """Run a one-off pipeline without pre-defining it.

    Exports from the first environment in stages, then sequentially deploys
    to each subsequent environment using the same orchestration as run_pipeline.

    Args:
        stages: Ordered list of environment names (2-20 entries, no duplicates).
        uuids: List of UUIDs to export (1-100 entries).
        export_type: Either "package" or "application".
        export_name: Name for the export deployment (max 256 chars).
        deploy_name: Optional template for import deployment names.
            Supports {environment} and {stage_number} placeholders.
        customization_file_path: Optional path to .properties ICF file.
        inspect_before_deploy: Whether to inspect before each import (default true).
        approval_environments: Optional list of environment names requiring approval.
            Must be a subset of stages.

    Returns:
        Dict with run_id and initial status, or an error dict if validation fails.
    """
    # Validate stages against configured environments
    environments = get_environments()
    validation_error = validate_pipeline_stages(stages, environments)
    if validation_error is not None:
        return validation_error

    # Also validate approval_environments against configured environments
    approval_envs = approval_environments or []
    if approval_envs:
        invalid_approval_envs = [
            env for env in approval_envs if env not in environments
        ]
        if invalid_approval_envs:
            return {
                "error": f"Invalid environment names in approval_environments: "
                f"{', '.join(invalid_approval_envs)}"
            }

    # Validate run parameters (min_stages=2 for ad-hoc)
    validation_error = validate_run_params(
        uuids=uuids,
        export_type=export_type,
        stages=stages,
        approval_environments=approval_envs,
        min_stages=2,
    )
    if validation_error is not None:
        return validation_error

    # Create run config
    config = RunConfig(
        uuids=uuids,
        export_type=export_type,
        export_name=export_name,
        deploy_name_template=deploy_name,
        customization_file_path=customization_file_path,
        inspect_before_deploy=inspect_before_deploy,
        approval_environments=approval_envs,
    )

    # Create the run with pipeline_name="__adhoc__"
    store = get_pipeline_store()
    run = store.create_run(
        definition_name="__adhoc__",
        config=config,
        stages=stages,
    )

    # Launch engine execution as a background task
    engine = get_pipeline_engine()
    asyncio.create_task(engine.execute(run.run_id))

    return {
        "run_id": run.run_id,
        "pipeline_name": run.pipeline_name,
        "status": run.status.value,
    }


@mcp.tool()
async def get_pipeline_run_status(run_id: str) -> dict:
    """Get the full status of a pipeline run including all stages and results.

    Args:
        run_id: The unique identifier of the pipeline run.

    Returns:
        Full pipeline run status including stages and results,
        or an error dict if the run is not found.
    """
    store = get_pipeline_store()
    run = store.get_run(run_id)

    if run is None:
        return {"error": f"Pipeline run '{run_id}' not found."}

    return _serialize_run(run)


@mcp.tool()
async def list_pipeline_runs() -> list[dict]:
    """List recent pipeline runs with their IDs, names, and statuses.

    Returns:
        List of run summaries (up to 100 most recent), each with
        run_id, pipeline_name, and status.
    """
    store = get_pipeline_store()
    runs = store.list_runs()

    return [
        {
            "run_id": r.run_id,
            "pipeline_name": r.pipeline_name,
            "status": r.status.value,
        }
        for r in runs
    ]


@mcp.tool()
async def cancel_pipeline_run(
    run_id: str,
    reason: str | None = None,
) -> dict:
    """Cancel a running pipeline to stop further promotion.

    Args:
        run_id: The unique identifier of the pipeline run to cancel.
        reason: Optional reason for cancellation (max 500 characters).

    Returns:
        Updated pipeline run status, or an error dict if the run is not found
        or already in a terminal state.
    """
    store = get_pipeline_store()
    run = store.get_run(run_id)

    if run is None:
        return {"error": f"Pipeline run '{run_id}' not found."}

    # Check if already in a terminal status
    if run.status in _TERMINAL_STATUSES:
        return {
            "error": f"Pipeline run has already terminated with status "
            f"'{run.status.value}'. Cannot cancel.",
            "status": run.status.value,
        }

    # Set cancellation reason
    if reason:
        run.cancellation_reason = reason[:500]

    # Signal the cancel event — the engine will pick this up
    run._cancel_event.set()

    # Also mark pending stages as SKIPPED and set status immediately
    # for responsiveness (engine will also do this, but we want immediate feedback)
    run.status = PipelineStatus.CANCELLED
    for stage in run.stages:
        if stage.status == StageStatus.PENDING:
            stage.status = StageStatus.SKIPPED

    return _serialize_run(run)
