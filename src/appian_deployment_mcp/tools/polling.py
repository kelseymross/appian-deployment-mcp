"""MCP tools for polling deployment and inspection status."""

import asyncio
import time

from ..client import AppianClient
from ..config import resolve_environment
from ..server import get_environments, mcp

DEPLOYMENT_TERMINAL_STATUSES = {
    "COMPLETED",
    "COMPLETED_WITH_ERRORS",
    "COMPLETED_WITH_IMPORT_ERRORS",
    "COMPLETED_WITH_PUBLISH_ERRORS",
    "COMPLETED_WITH_EXPORT_ERRORS",
    "FAILED",
    "REJECTED",
}

INSPECTION_TERMINAL_STATUSES = {"COMPLETED", "FAILED"}


@mcp.tool()
async def poll_deployment_status(
    deployment_uuid: str,
    poll_interval_seconds: int = 5,
    max_wait_seconds: int = 300,
    environment: str | None = None,
) -> dict:
    """Poll a deployment until it reaches a terminal status or times out.

    Args:
        deployment_uuid: The UUID of the deployment to poll.
        poll_interval_seconds: Seconds to wait between status checks (default 5).
        max_wait_seconds: Maximum seconds to wait before timing out (default 300).
        environment: Optional environment name. Uses the default environment if not specified.

    Returns:
        A dict with completed (bool), timed_out (bool), elapsed_seconds (float),
        and result (the last API response).
    """
    config = resolve_environment(get_environments(), environment)
    client = AppianClient(config)
    try:
        start = time.monotonic()
        result: dict = {}
        while True:
            result = await client.get(f"/deployments/{deployment_uuid}")

            if result.get("error"):
                return {
                    "completed": True,
                    "timed_out": False,
                    "elapsed_seconds": round(time.monotonic() - start, 2),
                    "result": result,
                }

            status = result.get("status", "")
            if status in DEPLOYMENT_TERMINAL_STATUSES:
                return {
                    "completed": True,
                    "timed_out": False,
                    "elapsed_seconds": round(time.monotonic() - start, 2),
                    "result": result,
                }

            elapsed = time.monotonic() - start
            if elapsed >= max_wait_seconds:
                return {
                    "completed": False,
                    "timed_out": True,
                    "elapsed_seconds": round(elapsed, 2),
                    "result": result,
                }

            await asyncio.sleep(poll_interval_seconds)
    finally:
        await client.close()


@mcp.tool()
async def poll_inspection_status(
    inspection_uuid: str,
    poll_interval_seconds: int = 5,
    max_wait_seconds: int = 300,
    environment: str | None = None,
) -> dict:
    """Poll an inspection until it reaches a terminal status or times out.

    Args:
        inspection_uuid: The UUID of the inspection to poll.
        poll_interval_seconds: Seconds to wait between status checks (default 5).
        max_wait_seconds: Maximum seconds to wait before timing out (default 300).
        environment: Optional environment name. Uses the default environment if not specified.

    Returns:
        A dict with completed (bool), timed_out (bool), elapsed_seconds (float),
        and result (the last API response).
    """
    config = resolve_environment(get_environments(), environment)
    client = AppianClient(config)
    try:
        start = time.monotonic()
        result: dict = {}
        while True:
            result = await client.get(f"/inspections/{inspection_uuid}")

            if result.get("error"):
                return {
                    "completed": True,
                    "timed_out": False,
                    "elapsed_seconds": round(time.monotonic() - start, 2),
                    "result": result,
                }

            status = result.get("status", "")
            if status in INSPECTION_TERMINAL_STATUSES:
                return {
                    "completed": True,
                    "timed_out": False,
                    "elapsed_seconds": round(time.monotonic() - start, 2),
                    "result": result,
                }

            elapsed = time.monotonic() - start
            if elapsed >= max_wait_seconds:
                return {
                    "completed": False,
                    "timed_out": True,
                    "elapsed_seconds": round(elapsed, 2),
                    "result": result,
                }

            await asyncio.sleep(poll_interval_seconds)
    finally:
        await client.close()
