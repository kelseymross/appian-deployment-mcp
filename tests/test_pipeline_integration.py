"""Integration tests for full pipeline execution with mocked API.

Tests end-to-end pipeline scenarios using respx to mock HTTP responses from
the Appian Deployment API. Each test exercises the PipelineEngine with a
realistic multi-environment configuration.

Requirements validated: 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 2.12,
                        8.1, 8.2, 8.3, 8.5
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from appian_deployment_mcp.config import EnvironmentConfig
from appian_deployment_mcp.pipeline.engine import PipelineEngine
from appian_deployment_mcp.pipeline.models import (
    PipelineStatus,
    RunConfig,
    StageOperation,
    StageStatus,
)
from appian_deployment_mcp.pipeline.store import PipelineStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ENVS = ["dev", "test", "prod"]


def _make_env_config(name: str) -> EnvironmentConfig:
    """Create a test EnvironmentConfig for a given environment name."""
    return EnvironmentConfig(
        name=name,
        domain=f"{name}.appiancloud.com",
        api_key=f"test-key-{name}",
    )


def _build_environments(names: list[str]) -> dict[str, EnvironmentConfig]:
    return {name: _make_env_config(name) for name in names}


def _base_url(env_name: str) -> str:
    return f"https://{env_name}.appiancloud.com/suite/deployment-management/v2"


def _mock_export_success(router, env_name: str, export_uuid: str = "export-uuid-001") -> None:
    """Mock a successful export: POST → poll → download."""
    base = _base_url(env_name)
    router.post(f"{base}/deployments").mock(
        return_value=httpx.Response(200, json={"uuid": export_uuid, "status": "IN_PROGRESS"})
    )
    router.get(f"{base}/deployments/{export_uuid}").mock(
        return_value=httpx.Response(200, json={
            "uuid": export_uuid,
            "status": "COMPLETED",
            "packageZip": f"{base}/deployments/{export_uuid}/package",
            "deploymentLogUrl": f"{base}/deployments/{export_uuid}/log",
        })
    )
    router.get(f"{base}/deployments/{export_uuid}/package").mock(
        return_value=httpx.Response(200, content=b"PK\x03\x04fake-zip-content")
    )


def _mock_export_failure(router, env_name: str, status: str = "FAILED") -> None:
    """Mock a failed export."""
    base = _base_url(env_name)
    export_uuid = "export-uuid-fail"
    router.post(f"{base}/deployments").mock(
        return_value=httpx.Response(200, json={"uuid": export_uuid, "status": "IN_PROGRESS"})
    )
    router.get(f"{base}/deployments/{export_uuid}").mock(
        return_value=httpx.Response(200, json={
            "uuid": export_uuid,
            "status": status,
            "deploymentLogUrl": f"{base}/deployments/{export_uuid}/log",
        })
    )


def _mock_inspect_success(router, env_name: str) -> None:
    """Mock a successful inspection."""
    base = _base_url(env_name)
    uuid = f"inspect-uuid-{env_name}"
    router.post(f"{base}/inspections").mock(
        return_value=httpx.Response(200, json={"uuid": uuid, "status": "IN_PROGRESS"})
    )
    router.get(f"{base}/inspections/{uuid}").mock(
        return_value=httpx.Response(200, json={
            "uuid": uuid,
            "status": "COMPLETED",
            "errors": [],
            "warnings": [],
            "objectCounts": {"expected": 10, "failed": 0, "skipped": 0},
        })
    )


def _mock_inspect_failure(router, env_name: str, status: str = "FAILED") -> None:
    """Mock a failed inspection."""
    base = _base_url(env_name)
    uuid = f"inspect-uuid-{env_name}-fail"
    router.post(f"{base}/inspections").mock(
        return_value=httpx.Response(200, json={"uuid": uuid, "status": "IN_PROGRESS"})
    )
    router.get(f"{base}/inspections/{uuid}").mock(
        return_value=httpx.Response(200, json={
            "uuid": uuid,
            "status": status,
            "errors": [{"objectName": "MyRule", "message": "Missing dependency"}],
            "warnings": [{"objectName": "MyInterface", "message": "Deprecated usage"}],
            "objectCounts": {"expected": 10, "failed": 1, "skipped": 0},
        })
    )


def _mock_import_success(router, env_name: str) -> None:
    """Mock a successful import."""
    base = _base_url(env_name)
    uuid = f"import-uuid-{env_name}"
    router.post(f"{base}/deployments").mock(
        return_value=httpx.Response(200, json={"uuid": uuid, "status": "IN_PROGRESS"})
    )
    router.get(f"{base}/deployments/{uuid}").mock(
        return_value=httpx.Response(200, json={
            "uuid": uuid,
            "status": "COMPLETED",
            "deploymentLogUrl": f"{base}/deployments/{uuid}/log",
            "objectCounts": {"expected": 10, "failed": 0, "skipped": 0},
        })
    )


def _mock_import_failure(router, env_name: str, status: str = "FAILED") -> None:
    """Mock a failed import."""
    base = _base_url(env_name)
    uuid = f"import-uuid-{env_name}-fail"
    router.post(f"{base}/deployments").mock(
        return_value=httpx.Response(200, json={"uuid": uuid, "status": "IN_PROGRESS"})
    )
    router.get(f"{base}/deployments/{uuid}").mock(
        return_value=httpx.Response(200, json={
            "uuid": uuid,
            "status": status,
            "deploymentLogUrl": f"{base}/deployments/{uuid}/log",
            "objectCounts": {"expected": 10, "failed": 3, "skipped": 2},
        })
    )


# ---------------------------------------------------------------------------
# Test: Successful 3-environment pipeline
# (export from dev → inspect+import to test → inspect+import to prod)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_3_environment_pipeline():
    """Full pipeline: export from dev, inspect+import to test, inspect+import to prod.

    Validates: Requirements 2.4, 2.5, 2.7, 2.10, 2.12
    """
    environments = _build_environments(ENVS)
    store = PipelineStore()
    engine = PipelineEngine(environments=environments, store=store)

    config = RunConfig(
        uuids=["uuid-001", "uuid-002"],
        export_type="package",
        export_name="my-export",
        inspect_before_deploy=True,
        approval_environments=[],
    )
    run = store.create_run("my-pipeline", config, ENVS)

    with respx.mock(assert_all_called=False) as router:
        # dev: export succeeds
        _mock_export_success(router, "dev")
        # test: inspect + import succeed
        _mock_inspect_success(router, "test")
        _mock_import_success(router, "test")
        # prod: inspect + import succeed
        _mock_inspect_success(router, "prod")
        _mock_import_success(router, "prod")

        await engine.execute(run.run_id)

    # Overall run completed
    assert run.status == PipelineStatus.COMPLETED
    assert run.completed_at is not None

    # Stage 1 (dev): export completed
    assert run.stages[0].status == StageStatus.COMPLETED
    assert run.stages[0].operation == StageOperation.EXPORT
    assert run.stages[0].result is not None
    assert run.stages[0].result.deployment_uuid == "export-uuid-001"
    assert run.stages[0].result.status == "COMPLETED"

    # Stage 2 (test): import completed
    assert run.stages[1].status == StageStatus.COMPLETED
    assert run.stages[1].operation == StageOperation.IMPORT
    assert run.stages[1].result is not None
    assert run.stages[1].result.deployment_uuid == f"import-uuid-test"
    assert run.stages[1].result.status == "COMPLETED"

    # Stage 3 (prod): import completed
    assert run.stages[2].status == StageStatus.COMPLETED
    assert run.stages[2].operation == StageOperation.IMPORT
    assert run.stages[2].result is not None
    assert run.stages[2].result.deployment_uuid == f"import-uuid-prod"
    assert run.stages[2].result.status == "COMPLETED"


# ---------------------------------------------------------------------------
# Test: Pipeline halting on export failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_halts_on_export_failure():
    """Pipeline halts when export fails with FAILED status.

    Validates: Requirements 2.6, 8.1
    """
    environments = _build_environments(ENVS)
    store = PipelineStore()
    engine = PipelineEngine(environments=environments, store=store)

    config = RunConfig(
        uuids=["uuid-001"],
        export_type="package",
        export_name="my-export",
        inspect_before_deploy=True,
    )
    run = store.create_run("my-pipeline", config, ENVS)

    with respx.mock(assert_all_called=False) as router:
        _mock_export_failure(router, "dev", status="FAILED")

        await engine.execute(run.run_id)

    # Run is FAILED
    assert run.status == PipelineStatus.FAILED
    assert run.completed_at is not None

    # Export stage is FAILED with error details
    export_stage = run.stages[0]
    assert export_stage.status == StageStatus.FAILED
    assert export_stage.result is not None
    assert export_stage.result.operation == StageOperation.EXPORT
    assert export_stage.result.deployment_uuid == "export-uuid-fail"
    assert export_stage.result.status == "FAILED"
    assert export_stage.result.deployment_log_url is not None

    # Subsequent stages remain PENDING (not executed)
    assert run.stages[1].status == StageStatus.PENDING
    assert run.stages[2].status == StageStatus.PENDING


@pytest.mark.asyncio
async def test_pipeline_halts_on_export_failure_with_export_errors():
    """Pipeline halts when export fails with COMPLETED_WITH_EXPORT_ERRORS.

    Validates: Requirements 2.6, 8.1
    """
    environments = _build_environments(ENVS)
    store = PipelineStore()
    engine = PipelineEngine(environments=environments, store=store)

    config = RunConfig(
        uuids=["uuid-001"],
        export_type="application",
        export_name="my-export",
        inspect_before_deploy=True,
    )
    run = store.create_run("my-pipeline", config, ENVS)

    with respx.mock(assert_all_called=False) as router:
        _mock_export_failure(router, "dev", status="COMPLETED_WITH_EXPORT_ERRORS")

        await engine.execute(run.run_id)

    assert run.status == PipelineStatus.FAILED
    export_stage = run.stages[0]
    assert export_stage.status == StageStatus.FAILED
    assert export_stage.result.status == "COMPLETED_WITH_EXPORT_ERRORS"
    assert export_stage.result.deployment_log_url is not None


# ---------------------------------------------------------------------------
# Test: Pipeline halting on inspection failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_halts_on_inspection_failure():
    """Pipeline halts when inspection fails at the first target environment.

    Validates: Requirements 2.8, 8.2
    """
    environments = _build_environments(ENVS)
    store = PipelineStore()
    engine = PipelineEngine(environments=environments, store=store)

    config = RunConfig(
        uuids=["uuid-001"],
        export_type="package",
        export_name="my-export",
        inspect_before_deploy=True,
    )
    run = store.create_run("my-pipeline", config, ENVS)

    with respx.mock(assert_all_called=False) as router:
        _mock_export_success(router, "dev")
        _mock_inspect_failure(router, "test", status="FAILED")

        await engine.execute(run.run_id)

    # Run is FAILED
    assert run.status == PipelineStatus.FAILED

    # Export stage completed
    assert run.stages[0].status == StageStatus.COMPLETED

    # Inspection stage is FAILED with error details
    inspect_stage = run.stages[1]
    assert inspect_stage.status == StageStatus.FAILED
    assert inspect_stage.result is not None
    assert inspect_stage.result.operation == StageOperation.INSPECT
    assert inspect_stage.result.deployment_uuid == "inspect-uuid-test-fail"
    assert inspect_stage.result.status == "FAILED"
    assert inspect_stage.result.errors is not None
    assert len(inspect_stage.result.errors) == 1
    assert inspect_stage.result.errors[0]["objectName"] == "MyRule"
    assert inspect_stage.result.warnings is not None
    assert len(inspect_stage.result.warnings) == 1
    assert inspect_stage.result.object_counts == {"expected": 10, "failed": 1, "skipped": 0}

    # Prod stage remains PENDING
    assert run.stages[2].status == StageStatus.PENDING


# ---------------------------------------------------------------------------
# Test: Pipeline halting on import failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_halts_on_import_failure():
    """Pipeline halts when import fails at a target environment.

    Validates: Requirements 2.11, 8.3
    """
    environments = _build_environments(ENVS)
    store = PipelineStore()
    engine = PipelineEngine(environments=environments, store=store)

    config = RunConfig(
        uuids=["uuid-001"],
        export_type="package",
        export_name="my-export",
        inspect_before_deploy=True,
    )
    run = store.create_run("my-pipeline", config, ENVS)

    with respx.mock(assert_all_called=False) as router:
        _mock_export_success(router, "dev")
        # test: inspection passes, import fails
        _mock_inspect_success(router, "test")
        _mock_import_failure(router, "test", status="COMPLETED_WITH_IMPORT_ERRORS")

        await engine.execute(run.run_id)

    # Run is FAILED
    assert run.status == PipelineStatus.FAILED

    # Export stage completed
    assert run.stages[0].status == StageStatus.COMPLETED

    # Import stage is FAILED with error details
    import_stage = run.stages[1]
    assert import_stage.status == StageStatus.FAILED
    assert import_stage.result is not None
    assert import_stage.result.operation == StageOperation.IMPORT
    assert import_stage.result.deployment_uuid == "import-uuid-test-fail"
    assert import_stage.result.status == "COMPLETED_WITH_IMPORT_ERRORS"
    assert import_stage.result.deployment_log_url is not None
    assert import_stage.result.object_counts == {"expected": 10, "failed": 3, "skipped": 2}

    # Prod stage remains PENDING
    assert run.stages[2].status == StageStatus.PENDING


# ---------------------------------------------------------------------------
# Test: Approval gate flow (pause, approve, continue)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approval_gate_pause_approve_continue():
    """Pipeline pauses at approval gate, resumes on approval, completes.

    Validates: Requirements 2.9, 2.10, 2.12
    """
    environments = _build_environments(ENVS)
    store = PipelineStore()
    engine = PipelineEngine(environments=environments, store=store)

    config = RunConfig(
        uuids=["uuid-001"],
        export_type="package",
        export_name="my-export",
        inspect_before_deploy=True,
        approval_environments=["prod"],
    )
    run = store.create_run("my-pipeline", config, ENVS)
    run_id = run.run_id

    async def approve_when_awaiting():
        """Monitor and approve when pipeline reaches AWAITING_APPROVAL."""
        while True:
            current_run = store.get_run(run_id)
            if current_run is None:
                break
            if current_run.status == PipelineStatus.AWAITING_APPROVAL:
                # Verify it paused at the right environment
                # The prod stage should still be pending for import
                assert current_run.stages[2].environment == "prod"
                # Grant approval
                current_run._approval_granted = True
                current_run._approval_event.set()
                break
            if current_run.status in (
                PipelineStatus.COMPLETED,
                PipelineStatus.FAILED,
                PipelineStatus.CANCELLED,
            ):
                break
            await asyncio.sleep(0.001)

    with respx.mock(assert_all_called=False) as router:
        _mock_export_success(router, "dev")
        _mock_inspect_success(router, "test")
        _mock_import_success(router, "test")
        _mock_inspect_success(router, "prod")
        _mock_import_success(router, "prod")

        engine_task = asyncio.create_task(engine.execute(run_id))
        approve_task = asyncio.create_task(approve_when_awaiting())

        await asyncio.wait_for(engine_task, timeout=10.0)
        approve_task.cancel()
        try:
            await approve_task
        except asyncio.CancelledError:
            pass

    # Pipeline completed successfully after approval
    assert run.status == PipelineStatus.COMPLETED
    assert run.stages[0].status == StageStatus.COMPLETED  # dev export
    assert run.stages[1].status == StageStatus.COMPLETED  # test import
    assert run.stages[2].status == StageStatus.COMPLETED  # prod import


# ---------------------------------------------------------------------------
# Test: Approval gate rejection (pause, reject, cancel)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approval_gate_rejection():
    """Pipeline pauses at approval gate, rejection cancels the pipeline.

    Validates: Requirements 2.9
    """
    environments = _build_environments(ENVS)
    store = PipelineStore()
    engine = PipelineEngine(environments=environments, store=store)

    config = RunConfig(
        uuids=["uuid-001"],
        export_type="package",
        export_name="my-export",
        inspect_before_deploy=True,
        approval_environments=["prod"],
    )
    run = store.create_run("my-pipeline", config, ENVS)
    run_id = run.run_id

    async def reject_when_awaiting():
        """Monitor and reject when pipeline reaches AWAITING_APPROVAL."""
        while True:
            current_run = store.get_run(run_id)
            if current_run is None:
                break
            if current_run.status == PipelineStatus.AWAITING_APPROVAL:
                # Reject the approval
                current_run._approval_granted = False
                current_run.rejection_reason = "Not ready for production"
                current_run._approval_event.set()
                break
            if current_run.status in (
                PipelineStatus.COMPLETED,
                PipelineStatus.FAILED,
                PipelineStatus.CANCELLED,
            ):
                break
            await asyncio.sleep(0.001)

    with respx.mock(assert_all_called=False) as router:
        _mock_export_success(router, "dev")
        _mock_inspect_success(router, "test")
        _mock_import_success(router, "test")
        _mock_inspect_success(router, "prod")
        # No import mock for prod — it should never be reached

        engine_task = asyncio.create_task(engine.execute(run_id))
        reject_task = asyncio.create_task(reject_when_awaiting())

        await asyncio.wait_for(engine_task, timeout=10.0)
        reject_task.cancel()
        try:
            await reject_task
        except asyncio.CancelledError:
            pass

    # Pipeline is CANCELLED due to rejection
    assert run.status == PipelineStatus.CANCELLED
    # Dev export completed
    assert run.stages[0].status == StageStatus.COMPLETED
    # Test import completed
    assert run.stages[1].status == StageStatus.COMPLETED
    # Prod stage was already INSPECTING when rejection occurred (inspection runs
    # before the approval gate), so it stays in that state — only PENDING stages
    # get marked SKIPPED on cancellation.
    assert run.stages[2].status == StageStatus.INSPECTING


# ---------------------------------------------------------------------------
# Test: Cancellation during execution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancellation_during_execution():
    """Pipeline is cancelled mid-execution; remaining stages are SKIPPED.

    Validates: Requirements 2.9
    """
    environments = _build_environments(ENVS)
    store = PipelineStore()
    engine = PipelineEngine(environments=environments, store=store)

    config = RunConfig(
        uuids=["uuid-001"],
        export_type="package",
        export_name="my-export",
        inspect_before_deploy=False,
        approval_environments=[],
    )
    run = store.create_run("my-pipeline", config, ENVS)
    run_id = run.run_id

    # We'll cancel after the export completes but before the first import finishes.
    # Use a side effect on the test env import POST to trigger cancellation.

    def _import_post_side_effect(request: httpx.Request) -> httpx.Response:
        """When test env import is posted, signal cancellation."""
        # This is an import POST — trigger cancel
        run._cancel_event.set()
        return httpx.Response(200, json={"uuid": "import-uuid-test", "status": "IN_PROGRESS"})

    def _import_poll_side_effect(request: httpx.Request) -> httpx.Response:
        """Return IN_PROGRESS so the engine has a chance to check cancellation."""
        return httpx.Response(200, json={"status": "IN_PROGRESS"})

    with respx.mock(assert_all_called=False) as router:
        base_test = _base_url("test")

        # Dev export succeeds
        _mock_export_success(router, "dev")

        # Test import: use side effects to trigger cancellation
        router.post(f"{base_test}/deployments").mock(side_effect=_import_post_side_effect)
        router.get(f"{base_test}/deployments/import-uuid-test").mock(
            side_effect=_import_poll_side_effect
        )

        await engine.execute(run_id)

    # Pipeline is CANCELLED
    assert run.status == PipelineStatus.CANCELLED

    # Dev export completed
    assert run.stages[0].status == StageStatus.COMPLETED

    # Remaining stages should be SKIPPED or CANCELLED
    # The test stage might be CANCELLED (was in progress) or SKIPPED
    # The prod stage should be SKIPPED
    assert run.stages[2].status == StageStatus.SKIPPED


# ---------------------------------------------------------------------------
# Test: Network error handling during stage execution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_network_error_during_export_download():
    """Network error during export artifact download records error_type and error_domain.

    The engine's outer except catches httpx.ConnectError from download_file,
    which re-raises network errors unlike other client methods.

    Validates: Requirements 8.5
    """
    environments = _build_environments(ENVS)
    store = PipelineStore()
    engine = PipelineEngine(environments=environments, store=store)

    config = RunConfig(
        uuids=["uuid-001"],
        export_type="package",
        export_name="my-export",
        inspect_before_deploy=True,
    )
    run = store.create_run("my-pipeline", config, ENVS)

    with respx.mock(assert_all_called=False) as router:
        base_dev = _base_url("dev")
        export_uuid = "export-uuid-001"
        # Export POST and poll succeed
        router.post(f"{base_dev}/deployments").mock(
            return_value=httpx.Response(200, json={"uuid": export_uuid, "status": "IN_PROGRESS"})
        )
        router.get(f"{base_dev}/deployments/{export_uuid}").mock(
            return_value=httpx.Response(200, json={
                "uuid": export_uuid,
                "status": "COMPLETED",
                "packageZip": f"{base_dev}/deployments/{export_uuid}/package",
                "deploymentLogUrl": f"{base_dev}/deployments/{export_uuid}/log",
            })
        )
        # Download fails with network error
        router.get(f"{base_dev}/deployments/{export_uuid}/package").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        await engine.execute(run.run_id)

    # Run is FAILED
    assert run.status == PipelineStatus.FAILED

    # Export stage has network error details
    export_stage = run.stages[0]
    assert export_stage.status == StageStatus.FAILED
    assert export_stage.result is not None
    assert export_stage.result.error_type == "network_error"
    assert export_stage.result.error_domain == "dev.appiancloud.com"

    # Subsequent stages remain PENDING
    assert run.stages[1].status == StageStatus.PENDING
    assert run.stages[2].status == StageStatus.PENDING


@pytest.mark.asyncio
async def test_network_error_during_export_post():
    """Network error during export POST is caught by client and treated as API error.

    The client catches httpx.ConnectError and returns an error dict.
    The engine sees result.get("error") and marks the stage FAILED.

    Validates: Requirements 8.5
    """
    environments = _build_environments(ENVS)
    store = PipelineStore()
    engine = PipelineEngine(environments=environments, store=store)

    config = RunConfig(
        uuids=["uuid-001"],
        export_type="package",
        export_name="my-export",
        inspect_before_deploy=True,
    )
    run = store.create_run("my-pipeline", config, ENVS)

    with respx.mock(assert_all_called=False) as router:
        base_dev = _base_url("dev")
        # Simulate a network error on the export POST
        router.post(f"{base_dev}/deployments").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        await engine.execute(run.run_id)

    # Run is FAILED
    assert run.status == PipelineStatus.FAILED

    # Export stage is FAILED
    export_stage = run.stages[0]
    assert export_stage.status == StageStatus.FAILED
    assert export_stage.result is not None

    # Subsequent stages remain PENDING
    assert run.stages[1].status == StageStatus.PENDING
    assert run.stages[2].status == StageStatus.PENDING


@pytest.mark.asyncio
async def test_network_error_during_inspection():
    """Network error during inspection is caught by client and marks stage FAILED.

    Validates: Requirements 8.5
    """
    environments = _build_environments(ENVS)
    store = PipelineStore()
    engine = PipelineEngine(environments=environments, store=store)

    config = RunConfig(
        uuids=["uuid-001"],
        export_type="package",
        export_name="my-export",
        inspect_before_deploy=True,
    )
    run = store.create_run("my-pipeline", config, ENVS)

    with respx.mock(assert_all_called=False) as router:
        _mock_export_success(router, "dev")
        # Simulate network error on inspection POST for test env
        base_test = _base_url("test")
        router.post(f"{base_test}/inspections").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        await engine.execute(run.run_id)

    # Run is FAILED
    assert run.status == PipelineStatus.FAILED

    # Export completed
    assert run.stages[0].status == StageStatus.COMPLETED

    # Inspection stage is FAILED
    inspect_stage = run.stages[1]
    assert inspect_stage.status == StageStatus.FAILED
    assert inspect_stage.result is not None

    # Prod stage remains PENDING
    assert run.stages[2].status == StageStatus.PENDING


@pytest.mark.asyncio
async def test_network_error_during_import():
    """Network error during import is caught by client and marks stage FAILED.

    Validates: Requirements 8.5
    """
    environments = _build_environments(ENVS)
    store = PipelineStore()
    engine = PipelineEngine(environments=environments, store=store)

    config = RunConfig(
        uuids=["uuid-001"],
        export_type="package",
        export_name="my-export",
        inspect_before_deploy=True,
    )
    run = store.create_run("my-pipeline", config, ENVS)

    with respx.mock(assert_all_called=False) as router:
        _mock_export_success(router, "dev")
        _mock_inspect_success(router, "test")
        # Simulate network error on import POST for test env
        base_test = _base_url("test")
        router.post(f"{base_test}/deployments").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        await engine.execute(run.run_id)

    # Run is FAILED
    assert run.status == PipelineStatus.FAILED

    # Export completed
    assert run.stages[0].status == StageStatus.COMPLETED

    # Import stage is FAILED
    import_stage = run.stages[1]
    assert import_stage.status == StageStatus.FAILED
    assert import_stage.result is not None

    # Prod stage remains PENDING
    assert run.stages[2].status == StageStatus.PENDING


@pytest.mark.asyncio
async def test_timeout_error_during_export_download():
    """Timeout error during export download records error_type='timeout' and error_domain.

    Validates: Requirements 8.5
    """
    environments = _build_environments(ENVS)
    store = PipelineStore()
    engine = PipelineEngine(environments=environments, store=store)

    config = RunConfig(
        uuids=["uuid-001"],
        export_type="package",
        export_name="my-export",
        inspect_before_deploy=False,
    )
    run = store.create_run("my-pipeline", config, ENVS)

    with respx.mock(assert_all_called=False) as router:
        base_dev = _base_url("dev")
        export_uuid = "export-uuid-001"
        # Export POST and poll succeed
        router.post(f"{base_dev}/deployments").mock(
            return_value=httpx.Response(200, json={"uuid": export_uuid, "status": "IN_PROGRESS"})
        )
        router.get(f"{base_dev}/deployments/{export_uuid}").mock(
            return_value=httpx.Response(200, json={
                "uuid": export_uuid,
                "status": "COMPLETED",
                "packageZip": f"{base_dev}/deployments/{export_uuid}/package",
                "deploymentLogUrl": f"{base_dev}/deployments/{export_uuid}/log",
            })
        )
        # Download fails with timeout
        router.get(f"{base_dev}/deployments/{export_uuid}/package").mock(
            side_effect=httpx.TimeoutException("Read timed out")
        )

        await engine.execute(run.run_id)

    # Run is FAILED
    assert run.status == PipelineStatus.FAILED

    # Export stage has timeout error details
    export_stage = run.stages[0]
    assert export_stage.status == StageStatus.FAILED
    assert export_stage.result is not None
    assert export_stage.result.error_type == "timeout"
    assert export_stage.result.error_domain == "dev.appiancloud.com"
