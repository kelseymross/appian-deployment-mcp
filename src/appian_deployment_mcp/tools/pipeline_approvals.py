"""MCP tools for pipeline approval and rejection gates."""

from __future__ import annotations

from ..pipeline.models import PipelineStatus
from ..server import get_pipeline_store, mcp


@mcp.tool()
async def approve_pipeline_stage(
    run_id: str,
    comment: str | None = None,
) -> dict:
    """Approve a pipeline stage that is awaiting approval, resuming execution.

    When a pipeline run is paused at an approval gate, this tool grants
    approval and allows the pipeline to proceed with the import to the
    pending environment.

    Args:
        run_id: The unique identifier of the pipeline run to approve.
        comment: Optional approval comment (max 2000 characters).

    Returns:
        Updated pipeline run status with run_id and new status,
        or an error dict if the run is not found or not awaiting approval.
    """
    store = get_pipeline_store()
    run = store.get_run(run_id)

    if run is None:
        return {"error": f"Pipeline run '{run_id}' not found."}

    if run.status != PipelineStatus.AWAITING_APPROVAL:
        return {
            "error": f"Pipeline run is not awaiting approval. "
            f"Current status: '{run.status.value}'.",
            "status": run.status.value,
        }

    # Record approval
    run._approval_granted = True
    if comment:
        run.approval_comment = comment[:2000]

    # Signal the approval event so the engine resumes
    run._approval_event.set()

    return {
        "run_id": run.run_id,
        "pipeline_name": run.pipeline_name,
        "status": run.status.value,
        "approval_comment": run.approval_comment,
    }


@mcp.tool()
async def reject_pipeline_stage(
    run_id: str,
    reason: str | None = None,
) -> dict:
    """Reject a pipeline stage that is awaiting approval, cancelling the run.

    When a pipeline run is paused at an approval gate, this tool rejects
    the deployment and marks the pipeline run as cancelled.

    Args:
        run_id: The unique identifier of the pipeline run to reject.
        reason: Optional rejection reason (max 2000 characters).

    Returns:
        Updated pipeline run status with run_id, new status, and rejection reason,
        or an error dict if the run is not found or not awaiting approval.
    """
    store = get_pipeline_store()
    run = store.get_run(run_id)

    if run is None:
        return {"error": f"Pipeline run '{run_id}' not found."}

    if run.status != PipelineStatus.AWAITING_APPROVAL:
        return {
            "error": f"Pipeline run is not awaiting approval. "
            f"Current status: '{run.status.value}'.",
            "status": run.status.value,
        }

    # Record rejection
    run._approval_granted = False
    if reason:
        run.rejection_reason = reason[:2000]

    # Signal the approval event so the engine resumes (and sees rejection)
    run._approval_event.set()

    return {
        "run_id": run.run_id,
        "pipeline_name": run.pipeline_name,
        "status": run.status.value,
        "rejection_reason": run.rejection_reason,
    }
