"""MCP tools for managing deployments in PENDING_REVIEW status."""

from ..client import AppianClient
from ..config import resolve_environment
from ..server import get_environments, mcp


@mcp.tool()
async def approve_deployment(
    deployment_uuid: str,
    environment: str | None = None,
) -> dict:
    """Approve a deployment that is in PENDING_REVIEW status.

    When a deployment is pending review (requires manual approval before import),
    this tool approves it and allows the import to proceed.

    Args:
        deployment_uuid: The UUID of the deployment to approve.
        environment: Optional environment name. Uses the default environment if not specified.

    Returns:
        The updated deployment status, or an error dict.
    """
    config = resolve_environment(get_environments(), environment)
    client = AppianClient(config)
    try:
        # First check the deployment is actually in PENDING_REVIEW
        result = await client.get(f"/deployments/{deployment_uuid}")
        if result.get("error"):
            return result

        status = result.get("status")
        if status != "PENDING_REVIEW":
            return {
                "error": True,
                "message": f"Deployment is not pending review. Current status: {status}",
            }

        # Approve the deployment
        approve_result = await client.post_json(
            f"/deployments/{deployment_uuid}/approve",
            body={},
        )
        return approve_result
    finally:
        await client.close()


@mcp.tool()
async def reject_deployment(
    deployment_uuid: str,
    reason: str | None = None,
    environment: str | None = None,
) -> dict:
    """Reject a deployment that is in PENDING_REVIEW status.

    When a deployment is pending review, this tool rejects it and prevents
    the import from proceeding.

    Args:
        deployment_uuid: The UUID of the deployment to reject.
        reason: Optional reason for rejection.
        environment: Optional environment name. Uses the default environment if not specified.

    Returns:
        The updated deployment status, or an error dict.
    """
    config = resolve_environment(get_environments(), environment)
    client = AppianClient(config)
    try:
        # First check the deployment is actually in PENDING_REVIEW
        result = await client.get(f"/deployments/{deployment_uuid}")
        if result.get("error"):
            return result

        status = result.get("status")
        if status != "PENDING_REVIEW":
            return {
                "error": True,
                "message": f"Deployment is not pending review. Current status: {status}",
            }

        # Reject the deployment
        body: dict = {}
        if reason:
            body["reason"] = reason

        reject_result = await client.post_json(
            f"/deployments/{deployment_uuid}/reject",
            body=body,
        )
        return reject_result
    finally:
        await client.close()
