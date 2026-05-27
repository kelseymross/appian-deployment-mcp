"""Property-based tests for PipelineEngine.

Feature: deployment-pipeline, Property 7: Stage failure transitions run to FAILED
Feature: deployment-pipeline, Property 8: Approval environments pause at correct stages
Feature: deployment-pipeline, Property 14: Cancellation marks CANCELLED and skips pending stages
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
import respx
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from appian_deployment_mcp.config import EnvironmentConfig
from appian_deployment_mcp.pipeline.engine import PipelineEngine
from appian_deployment_mcp.pipeline.models import (
    PipelineRun,
    PipelineStatus,
    RunConfig,
    StageStatus,
)
from appian_deployment_mcp.pipeline.store import PipelineStore


def _make_env_config(name: str) -> EnvironmentConfig:
    """Create a test EnvironmentConfig for a given environment name."""
    return EnvironmentConfig(
        name=name,
        domain=f"{name}.appiancloud.com",
        api_key=f"test-key-{name}",
    )


# --- Shared strategies ---
# Use only ASCII lowercase letters to avoid IDNA/encoding issues with domain names
env_name_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz",
    min_size=3,
    max_size=10,
)

stages_strategy = st.lists(
    env_name_strategy,
    min_size=3,
    max_size=6,
    unique=True,
)


# ============================================================================
# Property 7: Stage failure transitions run to FAILED
# ============================================================================

# Strategies for failure statuses
_export_failure_statuses = st.sampled_from(["FAILED", "COMPLETED_WITH_EXPORT_ERRORS"])
_inspection_failure_statuses = st.just("FAILED")
_import_failure_statuses = st.sampled_from([
    "FAILED", "COMPLETED_WITH_ERRORS",
    "COMPLETED_WITH_IMPORT_ERRORS", "COMPLETED_WITH_PUBLISH_ERRORS",
])

# Strategy for pipeline stages (2-5 unique ASCII lowercase names)
_prop7_stages_strategy = st.lists(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=3, max_size=10),
    min_size=2,
    max_size=5,
    unique=True,
)


def _p7_mock_export_success(mock_router, env_config: EnvironmentConfig) -> None:
    """Mock a successful export."""
    base_url = env_config.base_url
    uuid = "export-uuid-success"
    mock_router.post(f"{base_url}/deployments").mock(
        return_value=httpx.Response(200, json={"uuid": uuid, "status": "IN_PROGRESS"})
    )
    mock_router.get(f"{base_url}/deployments/{uuid}").mock(
        return_value=httpx.Response(200, json={
            "uuid": uuid, "status": "COMPLETED",
            "packageZip": f"{base_url}/deployments/{uuid}/package",
            "deploymentLogUrl": f"{base_url}/deployments/{uuid}/log",
        })
    )
    mock_router.get(f"{base_url}/deployments/{uuid}/package").mock(
        return_value=httpx.Response(200, content=b"fake-zip-content")
    )


def _p7_mock_export_failure(mock_router, env_config: EnvironmentConfig, status: str) -> None:
    """Mock a failed export."""
    base_url = env_config.base_url
    uuid = "export-uuid-fail"
    mock_router.post(f"{base_url}/deployments").mock(
        return_value=httpx.Response(200, json={"uuid": uuid, "status": "IN_PROGRESS"})
    )
    mock_router.get(f"{base_url}/deployments/{uuid}").mock(
        return_value=httpx.Response(200, json={
            "uuid": uuid, "status": status,
            "deploymentLogUrl": f"{base_url}/deployments/{uuid}/log",
        })
    )


def _p7_mock_inspect_success(mock_router, env_config: EnvironmentConfig) -> None:
    """Mock a successful inspection."""
    base_url = env_config.base_url
    uuid = f"inspect-uuid-{env_config.name}"
    mock_router.post(f"{base_url}/inspections").mock(
        return_value=httpx.Response(200, json={"uuid": uuid, "status": "IN_PROGRESS"})
    )
    mock_router.get(f"{base_url}/inspections/{uuid}").mock(
        return_value=httpx.Response(200, json={
            "uuid": uuid, "status": "COMPLETED",
            "errors": [], "warnings": [],
            "objectCounts": {"expected": 5, "failed": 0, "skipped": 0},
        })
    )


def _p7_mock_inspect_failure(mock_router, env_config: EnvironmentConfig, status: str) -> None:
    """Mock a failed inspection."""
    base_url = env_config.base_url
    uuid = f"inspect-uuid-{env_config.name}-fail"
    mock_router.post(f"{base_url}/inspections").mock(
        return_value=httpx.Response(200, json={"uuid": uuid, "status": "IN_PROGRESS"})
    )
    mock_router.get(f"{base_url}/inspections/{uuid}").mock(
        return_value=httpx.Response(200, json={
            "uuid": uuid, "status": status,
            "errors": [{"objectName": "obj1", "message": "error msg"}],
            "warnings": [],
            "objectCounts": {"expected": 5, "failed": 1, "skipped": 0},
        })
    )


def _p7_mock_import_success(mock_router, env_config: EnvironmentConfig) -> None:
    """Mock a successful import."""
    base_url = env_config.base_url
    uuid = f"import-uuid-{env_config.name}"
    mock_router.post(f"{base_url}/deployments").mock(
        return_value=httpx.Response(200, json={"uuid": uuid, "status": "IN_PROGRESS"})
    )
    mock_router.get(f"{base_url}/deployments/{uuid}").mock(
        return_value=httpx.Response(200, json={
            "uuid": uuid, "status": "COMPLETED",
            "deploymentLogUrl": f"{base_url}/deployments/{uuid}/log",
            "objectCounts": {"expected": 5, "failed": 0, "skipped": 0},
        })
    )


def _p7_mock_import_failure(mock_router, env_config: EnvironmentConfig, status: str) -> None:
    """Mock a failed import."""
    base_url = env_config.base_url
    uuid = f"import-uuid-{env_config.name}-fail"
    mock_router.post(f"{base_url}/deployments").mock(
        return_value=httpx.Response(200, json={"uuid": uuid, "status": "IN_PROGRESS"})
    )
    mock_router.get(f"{base_url}/deployments/{uuid}").mock(
        return_value=httpx.Response(200, json={
            "uuid": uuid, "status": status,
            "deploymentLogUrl": f"{base_url}/deployments/{uuid}/log",
            "objectCounts": {"expected": 5, "failed": 2, "skipped": 1},
        })
    )


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    stages=_prop7_stages_strategy,
    failure_status=_export_failure_statuses,
)
@pytest.mark.asyncio
async def test_property7_export_failure_marks_run_failed(
    stages: list[str],
    failure_status: str,
):
    """Property 7: Export failure transitions run to FAILED.

    Feature: deployment-pipeline, Property 7: Stage failure transitions run to FAILED

    When export fails, run status is FAILED and no subsequent stages execute.

    **Validates: Requirements 2.6**
    """
    environments = {name: _make_env_config(name) for name in stages}
    store = PipelineStore()
    engine = PipelineEngine(environments=environments, store=store)
    config = RunConfig(
        uuids=["uuid-001"],
        export_type="package",
        export_name="test-export",
        inspect_before_deploy=True,
    )

    run = store.create_run("test-pipeline", config, stages)
    source_env = environments[stages[0]]

    with respx.mock(assert_all_mocked=False) as router:
        _p7_mock_export_failure(router, source_env, failure_status)
        await engine.execute(run.run_id)

    # Run status must be FAILED
    assert run.status == PipelineStatus.FAILED, (
        f"Expected FAILED but got {run.status} for failure_status={failure_status}"
    )
    # First stage (export) should be FAILED
    assert run.stages[0].status == StageStatus.FAILED
    # All subsequent stages should remain PENDING (not executed)
    for stage in run.stages[1:]:
        assert stage.status == StageStatus.PENDING, (
            f"Stage {stage.environment} should be PENDING but is {stage.status}"
        )


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(data=st.data())
@pytest.mark.asyncio
async def test_property7_inspection_failure_marks_run_failed(data: st.DataObject):
    """Property 7: Inspection failure transitions run to FAILED.

    Feature: deployment-pipeline, Property 7: Stage failure transitions run to FAILED

    When inspection fails at any target stage, run status is FAILED
    and no subsequent stages execute.

    **Validates: Requirements 2.8**
    """
    stages = data.draw(_prop7_stages_strategy)
    assume(len(stages) >= 3)  # Need at least source + 2 targets for meaningful test
    failure_status = data.draw(_inspection_failure_statuses)

    # Choose which target stage fails (1-indexed, within bounds)
    failure_stage_offset = data.draw(st.integers(min_value=1, max_value=len(stages) - 1))

    environments = {name: _make_env_config(name) for name in stages}
    store = PipelineStore()
    engine = PipelineEngine(environments=environments, store=store)
    config = RunConfig(
        uuids=["uuid-001"],
        export_type="package",
        export_name="test-export",
        inspect_before_deploy=True,
    )

    run = store.create_run("test-pipeline", config, stages)
    source_env = environments[stages[0]]

    with respx.mock(assert_all_mocked=False) as router:
        # Export always succeeds
        _p7_mock_export_success(router, source_env)

        # Mock stages before the failure stage as successful
        for i in range(1, failure_stage_offset):
            target_env = environments[stages[i]]
            _p7_mock_inspect_success(router, target_env)
            _p7_mock_import_success(router, target_env)

        # Mock the failing stage's inspection
        failing_env = environments[stages[failure_stage_offset]]
        _p7_mock_inspect_failure(router, failing_env, failure_status)

        await engine.execute(run.run_id)

    # Run status must be FAILED
    assert run.status == PipelineStatus.FAILED, (
        f"Expected FAILED but got {run.status} at stage {failure_stage_offset}"
    )
    # The failing stage should be FAILED
    assert run.stages[failure_stage_offset].status == StageStatus.FAILED
    # All stages after the failing one should remain PENDING
    for stage in run.stages[failure_stage_offset + 1:]:
        assert stage.status == StageStatus.PENDING, (
            f"Stage {stage.environment} should be PENDING but is {stage.status}"
        )


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(data=st.data())
@pytest.mark.asyncio
async def test_property7_import_failure_marks_run_failed(data: st.DataObject):
    """Property 7: Import failure transitions run to FAILED.

    Feature: deployment-pipeline, Property 7: Stage failure transitions run to FAILED

    When import fails at any target stage, run status is FAILED
    and no subsequent stages execute.

    **Validates: Requirements 2.11**
    """
    stages = data.draw(_prop7_stages_strategy)
    assume(len(stages) >= 3)  # Need at least source + 2 targets for meaningful test
    failure_status = data.draw(_import_failure_statuses)

    # Choose which target stage fails (1-indexed, within bounds)
    failure_stage_offset = data.draw(st.integers(min_value=1, max_value=len(stages) - 1))

    environments = {name: _make_env_config(name) for name in stages}
    store = PipelineStore()
    engine = PipelineEngine(environments=environments, store=store)
    config = RunConfig(
        uuids=["uuid-001"],
        export_type="package",
        export_name="test-export",
        inspect_before_deploy=True,
    )

    run = store.create_run("test-pipeline", config, stages)
    source_env = environments[stages[0]]

    with respx.mock(assert_all_mocked=False) as router:
        # Export always succeeds
        _p7_mock_export_success(router, source_env)

        # Mock stages before the failure stage as successful
        for i in range(1, failure_stage_offset):
            target_env = environments[stages[i]]
            _p7_mock_inspect_success(router, target_env)
            _p7_mock_import_success(router, target_env)

        # Mock the failing stage: inspection passes but import fails
        failing_env = environments[stages[failure_stage_offset]]
        _p7_mock_inspect_success(router, failing_env)
        _p7_mock_import_failure(router, failing_env, failure_status)

        await engine.execute(run.run_id)

    # Run status must be FAILED
    assert run.status == PipelineStatus.FAILED, (
        f"Expected FAILED but got {run.status} at stage {failure_stage_offset}"
    )
    # The failing stage should be FAILED
    assert run.stages[failure_stage_offset].status == StageStatus.FAILED
    # All stages after the failing one should remain PENDING
    for stage in run.stages[failure_stage_offset + 1:]:
        assert stage.status == StageStatus.PENDING, (
            f"Stage {stage.environment} should be PENDING but is {stage.status}"
        )


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    stages=_prop7_stages_strategy,
    failure_status=_import_failure_statuses,
)
@pytest.mark.asyncio
async def test_property7_import_failure_without_inspection(
    stages: list[str],
    failure_status: str,
):
    """Property 7: Import failure without inspection transitions run to FAILED.

    Feature: deployment-pipeline, Property 7: Stage failure transitions run to FAILED

    When inspect_before_deploy is False and import fails, run status is FAILED.

    **Validates: Requirements 2.11**
    """
    environments = {name: _make_env_config(name) for name in stages}
    store = PipelineStore()
    engine = PipelineEngine(environments=environments, store=store)
    config = RunConfig(
        uuids=["uuid-001"],
        export_type="package",
        export_name="test-export",
        inspect_before_deploy=False,
    )

    run = store.create_run("test-pipeline", config, stages)
    source_env = environments[stages[0]]
    failing_env = environments[stages[1]]

    with respx.mock(assert_all_mocked=False) as router:
        _p7_mock_export_success(router, source_env)
        _p7_mock_import_failure(router, failing_env, failure_status)
        await engine.execute(run.run_id)

    # Run status must be FAILED
    assert run.status == PipelineStatus.FAILED
    # First target stage should be FAILED
    assert run.stages[1].status == StageStatus.FAILED
    # All subsequent stages should remain PENDING
    for stage in run.stages[2:]:
        assert stage.status == StageStatus.PENDING, (
            f"Stage {stage.environment} should be PENDING but is {stage.status}"
        )


# ============================================================================
# Property 8: Approval environments pause at correct stages
# ============================================================================

# Counter for generating unique import UUIDs across test iterations
_import_counter = {"count": 0}


def _deployment_post_side_effect(request: httpx.Request) -> httpx.Response:
    """Side effect for deployment POST requests - distinguishes export vs import."""
    action_type = request.headers.get("action-type", "")
    if action_type == "export":
        return httpx.Response(
            200,
            json={"uuid": "export-uuid-001", "status": "IN_PROGRESS"},
        )
    else:
        _import_counter["count"] += 1
        uuid = f"import-uuid-{_import_counter['count']:03d}"
        return httpx.Response(
            200,
            json={"uuid": uuid, "status": "IN_PROGRESS"},
        )


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(data=st.data())
@pytest.mark.asyncio
async def test_property8_approval_environments_pause_at_correct_stages(data: st.DataObject):
    """Property 8: Approval environments pause at correct stages.

    Feature: deployment-pipeline, Property 8: Approval environments pause at correct stages

    For any pipeline run with approval_environments containing a subset of the
    pipeline's stages, the run SHALL transition to AWAITING_APPROVAL status exactly
    when execution reaches a stage whose environment is in approval_environments,
    and SHALL not advance past that stage until approval is granted.

    **Validates: Requirements 2.9**
    """
    # Generate stages (3-6 unique environment names)
    stages = data.draw(stages_strategy)
    assume(len(stages) >= 3)

    # Generate approval_environments as a non-empty subset of target stages (stages[1:])
    target_stages = stages[1:]
    approval_envs = data.draw(
        st.lists(
            st.sampled_from(target_stages),
            min_size=1,
            max_size=len(target_stages),
            unique=True,
        )
    )

    # Build environment configs for all stages
    environments = {name: _make_env_config(name) for name in stages}

    # Create store and run
    store = PipelineStore()
    config = RunConfig(
        uuids=["test-uuid-1"],
        export_type="package",
        export_name="test-export",
        inspect_before_deploy=False,
        approval_environments=approval_envs,
    )
    run = store.create_run("test-pipeline", config, stages)
    run_id = run.run_id

    engine = PipelineEngine(environments, store)

    # Track which environments the run paused at (in order)
    paused_environments: list[str] = []

    # Use a synchronization mechanism: the monitor signals when it has recorded
    # the pause and is ready for the engine to proceed.
    approval_processed = asyncio.Event()

    async def monitor_and_approve():
        """Monitor the run and approve when it pauses at AWAITING_APPROVAL.

        Uses a tight polling loop and proper synchronization to avoid race
        conditions between approval grants and the engine's next gate.
        """
        last_paused_env = None
        while True:
            current_run = store.get_run(run_id)
            if current_run is None:
                break

            if current_run.status == PipelineStatus.AWAITING_APPROVAL:
                # Find which environment we're paused at by looking at the
                # first PENDING stage that is in approval_envs. This is the
                # stage the engine is about to import to.
                paused_env = None
                for stage in current_run.stages:
                    if stage.status == StageStatus.PENDING and stage.environment in approval_envs:
                        paused_env = stage.environment
                        break

                # Only record if this is a new pause (not a duplicate detection)
                if paused_env and paused_env != last_paused_env:
                    paused_environments.append(paused_env)
                    last_paused_env = paused_env

                    # Grant approval: set the flag and signal the event
                    current_run._approval_granted = True
                    current_run._approval_event.set()

                    # Wait briefly for the engine to wake up and consume the approval
                    # before we yield control again
                    await asyncio.sleep(0)

            elif current_run.status in (
                PipelineStatus.COMPLETED,
                PipelineStatus.FAILED,
                PipelineStatus.CANCELLED,
            ):
                break

            await asyncio.sleep(0)

    # Mock all HTTP calls to succeed
    with respx.mock(assert_all_called=False) as mock:
        mock.post(url__regex=r".*/deployments").mock(
            side_effect=_deployment_post_side_effect
        )
        mock.get(url__regex=r".*/deployments/export-uuid-001").respond(
            200,
            json={
                "uuid": "export-uuid-001",
                "status": "COMPLETED",
                "packageZip": "/packages/export-uuid-001.zip",
            },
        )
        mock.get(url__regex=r".*/deployments/import-uuid-\d+").respond(
            200,
            json={"status": "COMPLETED", "deploymentLogUrl": "/logs/test"},
        )
        mock.get(url__regex=r".*/packages/.*\.zip").respond(
            200,
            content=b"fake-zip-content",
        )

        # Run engine and monitor concurrently
        engine_task = asyncio.create_task(engine.execute(run_id))
        monitor_task = asyncio.create_task(monitor_and_approve())

        try:
            await asyncio.wait_for(engine_task, timeout=10.0)
        except asyncio.TimeoutError:
            engine_task.cancel()
            pytest.fail("Engine execution timed out")
        finally:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

    # Verify: the run paused at exactly the approval environments in pipeline order
    expected_pause_order = [env for env in stages[1:] if env in approval_envs]
    assert paused_environments == expected_pause_order, (
        f"Expected pauses at {expected_pause_order} but got {paused_environments}. "
        f"Stages: {stages}, approval_envs: {approval_envs}"
    )

    # Verify: the run completed successfully (all approvals were granted)
    final_run = store.get_run(run_id)
    assert final_run is not None
    assert final_run.status == PipelineStatus.COMPLETED, (
        f"Expected COMPLETED but got {final_run.status}. "
        f"Stages: {[(s.environment, s.status) for s in final_run.stages]}"
    )


# ============================================================================
# Property 14: Cancellation marks CANCELLED and skips pending stages
# ============================================================================


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(data=st.data())
@pytest.mark.asyncio
async def test_property14_cancellation_marks_cancelled_and_skips_pending(
    data: st.DataObject,
):
    """Property 14: Cancellation marks CANCELLED and skips pending stages.

    Feature: deployment-pipeline, Property 14: Cancellation marks CANCELLED and skips pending stages

    For any pipeline run in IN_PROGRESS status with K remaining PENDING stages,
    signaling the cancel event SHALL set the run status to CANCELLED and all K
    pending stages SHALL have status SKIPPED.

    **Validates: Requirements 6.2, 6.4**
    """
    # Generate stages (3-6 unique environment names)
    stages = data.draw(stages_strategy)
    assume(len(stages) >= 3)

    # Choose at which target stage to trigger cancellation (1-indexed offset into stages)
    # cancel_before_stage means: allow (cancel_before_stage - 1) target imports to succeed,
    # then set the cancel event so the engine sees it before the next stage starts.
    cancel_before_stage = data.draw(
        st.integers(min_value=1, max_value=len(stages) - 1)
    )

    environments = {name: _make_env_config(name) for name in stages}
    store = PipelineStore()
    engine = PipelineEngine(environments=environments, store=store)
    config = RunConfig(
        uuids=["uuid-001"],
        export_type="package",
        export_name="test-export",
        inspect_before_deploy=False,
        approval_environments=[],
    )

    run = store.create_run("test-pipeline", config, stages)
    run_id = run.run_id

    # Use a deterministic approach: trigger cancellation via a side effect
    # when the Nth import's GET poll is called. This ensures the cancel event
    # is set at a deterministic point in the execution flow.
    import_post_count = {"value": 0}

    def _deployment_post_handler(request: httpx.Request) -> httpx.Response:
        """Handle deployment POST requests, triggering cancel at the right import."""
        action_type = request.headers.get("action-type", "")
        if action_type == "export":
            return httpx.Response(
                200,
                json={"uuid": "export-uuid-cancel", "status": "IN_PROGRESS"},
            )
        else:
            import_post_count["value"] += 1
            current_import = import_post_count["value"]

            # If this is the import at the cancel_before_stage position,
            # set the cancel event. The engine checks cancellation between
            # operations, but since we're already in the import, we need to
            # trigger it during the poll so the engine picks it up.
            if current_import == cancel_before_stage:
                # Set cancel event — the poll will return IN_PROGRESS and
                # the engine will check cancellation on next poll iteration
                run._cancel_event.set()

            uuid = f"import-uuid-cancel-{current_import:03d}"
            return httpx.Response(
                200,
                json={"uuid": uuid, "status": "IN_PROGRESS"},
            )

    def _import_get_handler(request: httpx.Request) -> httpx.Response:
        """Handle import GET poll requests — return COMPLETED for allowed imports."""
        # Extract the import number from the URL
        url_path = str(request.url)
        # If cancel event is set, the engine should detect it during poll
        # Return IN_PROGRESS to give the engine a chance to check cancellation
        if run._cancel_event.is_set():
            return httpx.Response(
                200,
                json={"status": "IN_PROGRESS"},
            )
        return httpx.Response(
            200,
            json={"status": "COMPLETED", "deploymentLogUrl": "/logs/test"},
        )

    with respx.mock(assert_all_called=False) as mock:
        mock.post(url__regex=r".*/deployments").mock(
            side_effect=_deployment_post_handler
        )
        mock.get(url__regex=r".*/deployments/export-uuid-cancel").respond(
            200,
            json={
                "uuid": "export-uuid-cancel",
                "status": "COMPLETED",
                "packageZip": "/packages/export-uuid-cancel.zip",
            },
        )
        mock.get(url__regex=r".*/deployments/import-uuid-cancel-\d+").mock(
            side_effect=_import_get_handler
        )
        mock.get(url__regex=r".*/packages/.*\.zip").respond(
            200,
            content=b"fake-zip-content",
        )

        await engine.execute(run_id)

    # Verify: the run status is CANCELLED
    final_run = store.get_run(run_id)
    assert final_run is not None
    assert final_run.status == PipelineStatus.CANCELLED, (
        f"Expected CANCELLED but got {final_run.status}. "
        f"cancel_before_stage={cancel_before_stage}, "
        f"Stages: {[(s.environment, s.status.value) for s in final_run.stages]}"
    )

    # Verify: all stages that were still PENDING when cancel was signaled are now SKIPPED
    for stage in final_run.stages:
        if stage.status == StageStatus.PENDING:
            pytest.fail(
                f"Stage {stage.environment} (#{stage.stage_number}) is still PENDING "
                f"after cancellation — should be SKIPPED. "
                f"All stages: {[(s.environment, s.status.value) for s in final_run.stages]}"
            )


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(data=st.data())
@pytest.mark.asyncio
async def test_property14_cancellation_during_approval_gate(
    data: st.DataObject,
):
    """Property 14: Cancellation during AWAITING_APPROVAL marks CANCELLED and skips pending.

    Feature: deployment-pipeline, Property 14: Cancellation marks CANCELLED and skips pending stages

    For any pipeline run in AWAITING_APPROVAL status with K remaining PENDING stages,
    signaling the cancel event SHALL set the run status to CANCELLED and all K
    pending stages SHALL have status SKIPPED.

    **Validates: Requirements 6.2, 6.4**
    """
    # Generate stages (3-6 unique environment names)
    stages = data.draw(stages_strategy)
    assume(len(stages) >= 3)

    # Pick which target stage has an approval gate where we'll cancel
    approval_stage_idx = data.draw(
        st.integers(min_value=1, max_value=len(stages) - 1)
    )
    approval_env = stages[approval_stage_idx]

    environments = {name: _make_env_config(name) for name in stages}
    store = PipelineStore()
    engine = PipelineEngine(environments=environments, store=store)
    config = RunConfig(
        uuids=["uuid-001"],
        export_type="package",
        export_name="test-export",
        inspect_before_deploy=False,
        approval_environments=[approval_env],
    )

    run = store.create_run("test-pipeline", config, stages)
    run_id = run.run_id

    import_counter_local = {"value": 0}

    def _deployment_post_handler(request: httpx.Request) -> httpx.Response:
        action_type = request.headers.get("action-type", "")
        if action_type == "export":
            return httpx.Response(
                200,
                json={"uuid": "export-uuid-appr", "status": "IN_PROGRESS"},
            )
        else:
            import_counter_local["value"] += 1
            uuid = f"import-uuid-appr-{import_counter_local['value']:03d}"
            return httpx.Response(
                200,
                json={"uuid": uuid, "status": "IN_PROGRESS"},
            )

    async def cancel_at_approval_gate():
        """Wait for the run to reach AWAITING_APPROVAL, then cancel."""
        while True:
            current_run = store.get_run(run_id)
            if current_run is None:
                break

            if current_run.status == PipelineStatus.AWAITING_APPROVAL:
                # Signal cancellation while at the approval gate
                await asyncio.sleep(0.005)
                current_run._cancel_event.set()
                break

            if current_run.status in (
                PipelineStatus.COMPLETED,
                PipelineStatus.FAILED,
                PipelineStatus.CANCELLED,
            ):
                break

            await asyncio.sleep(0.005)

    with respx.mock(assert_all_called=False) as mock:
        mock.post(url__regex=r".*/deployments").mock(
            side_effect=_deployment_post_handler
        )
        mock.get(url__regex=r".*/deployments/export-uuid-appr").respond(
            200,
            json={
                "uuid": "export-uuid-appr",
                "status": "COMPLETED",
                "packageZip": "/packages/export-uuid-appr.zip",
            },
        )
        mock.get(url__regex=r".*/deployments/import-uuid-appr-\d+").respond(
            200,
            json={"status": "COMPLETED", "deploymentLogUrl": "/logs/test"},
        )
        mock.get(url__regex=r".*/packages/.*\.zip").respond(
            200,
            content=b"fake-zip-content",
        )

        engine_task = asyncio.create_task(engine.execute(run_id))
        cancel_task = asyncio.create_task(cancel_at_approval_gate())

        try:
            await asyncio.wait_for(engine_task, timeout=10.0)
        except asyncio.TimeoutError:
            engine_task.cancel()
            pytest.fail("Engine execution timed out")
        finally:
            cancel_task.cancel()
            try:
                await cancel_task
            except asyncio.CancelledError:
                pass

    # Verify: the run status is CANCELLED
    final_run = store.get_run(run_id)
    assert final_run is not None
    assert final_run.status == PipelineStatus.CANCELLED, (
        f"Expected CANCELLED but got {final_run.status}. "
        f"Stages: {[(s.environment, s.status.value) for s in final_run.stages]}"
    )

    # Verify: all stages that were PENDING are now SKIPPED
    for stage in final_run.stages:
        if stage.status == StageStatus.PENDING:
            pytest.fail(
                f"Stage {stage.environment} (#{stage.stage_number}) is still PENDING "
                f"after cancellation — should be SKIPPED. "
                f"All stages: {[(s.environment, s.status.value) for s in final_run.stages]}"
            )

    # Verify: the approval stage and all subsequent stages should be SKIPPED
    # (since cancellation happened before import at the approval gate)
    for stage in final_run.stages[approval_stage_idx:]:
        assert stage.status == StageStatus.SKIPPED, (
            f"Stage {stage.environment} (#{stage.stage_number}) should be SKIPPED "
            f"but is {stage.status.value}. "
            f"All stages: {[(s.environment, s.status.value) for s in final_run.stages]}"
        )
