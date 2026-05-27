"""Property-based tests for pipeline status response structural completeness.

Feature: deployment-pipeline, Property 12: Status response structural completeness

For any pipeline run, the status response SHALL include the overall PipelineStatus,
pipeline name, and a list of stages. For each stage in a terminal state, the response
SHALL include the environment name, operation type, and final status. When the run is
in AWAITING_APPROVAL, the response SHALL additionally include the pending environment name.

**Validates: Requirements 4.2, 4.3, 4.4**
"""

from __future__ import annotations

from datetime import datetime

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from appian_deployment_mcp.pipeline.models import (
    PipelineRun,
    PipelineStage,
    PipelineStatus,
    RunConfig,
    StageOperation,
    StageResult,
    StageStatus,
)
from appian_deployment_mcp.pipeline.store import PipelineStore
from appian_deployment_mcp.tools.pipeline_runs import _serialize_run


# --- Strategies ---

# Terminal stage statuses (stages that have completed processing)
_TERMINAL_STAGE_STATUSES = [
    StageStatus.COMPLETED,
    StageStatus.FAILED,
    StageStatus.SKIPPED,
    StageStatus.CANCELLED,
]

# Non-terminal stage statuses (stages still in progress or pending)
_NON_TERMINAL_STAGE_STATUSES = [
    StageStatus.PENDING,
    StageStatus.EXPORTING,
    StageStatus.INSPECTING,
    StageStatus.DEPLOYING,
]

# All pipeline statuses
_ALL_PIPELINE_STATUSES = list(PipelineStatus)

# All stage operations
_ALL_OPERATIONS = list(StageOperation)

# Environment name strategy
env_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=20,
)

# Pipeline name strategy
pipeline_name_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        whitelist_characters="-_ ",
    ),
    min_size=1,
    max_size=128,
).filter(lambda s: s.strip() != "")

# RunConfig strategy
run_config_strategy = st.builds(
    RunConfig,
    uuids=st.lists(st.uuids().map(str), min_size=1, max_size=5),
    export_type=st.sampled_from(["package", "application"]),
    export_name=st.text(min_size=1, max_size=50),
    deploy_name_template=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
    customization_file_path=st.none(),
    inspect_before_deploy=st.booleans(),
    approval_environments=st.just([]),
)

# Stage list strategy (1-20 unique environment names)
stage_list_strategy = st.lists(
    env_name_strategy,
    min_size=1,
    max_size=10,
    unique=True,
)

# Strategy for a StageResult
stage_result_strategy = st.builds(
    StageResult,
    environment=env_name_strategy,
    operation=st.sampled_from(_ALL_OPERATIONS),
    deployment_uuid=st.one_of(st.none(), st.uuids().map(str)),
    status=st.text(min_size=1, max_size=30),
    package_path=st.none(),
    deployment_log_url=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
    errors=st.one_of(st.none(), st.lists(st.fixed_dictionaries({"message": st.text(min_size=1, max_size=20)}), max_size=3)),
    warnings=st.one_of(st.none(), st.lists(st.fixed_dictionaries({"message": st.text(min_size=1, max_size=20)}), max_size=3)),
    object_counts=st.one_of(st.none(), st.fixed_dictionaries({"expected": st.integers(0, 100), "failed": st.integers(0, 10), "skipped": st.integers(0, 10)})),
    error_type=st.one_of(st.none(), st.sampled_from(["network_error", "timeout"])),
    error_domain=st.one_of(st.none(), st.text(min_size=1, max_size=30)),
)


class TestProperty12StatusResponseStructuralCompleteness:
    """Property 12: Status response structural completeness.

    Feature: deployment-pipeline, Property 12: Status response structural completeness

    **Validates: Requirements 4.2, 4.3, 4.4**
    """

    @settings(max_examples=100)
    @given(
        pipeline_name=pipeline_name_strategy,
        pipeline_status=st.sampled_from(_ALL_PIPELINE_STATUSES),
        stages=stage_list_strategy,
        config=run_config_strategy,
    )
    def test_status_response_includes_required_top_level_fields(
        self,
        pipeline_name: str,
        pipeline_status: PipelineStatus,
        stages: list[str],
        config: RunConfig,
    ):
        """For any pipeline run, the status response SHALL include the overall
        PipelineStatus, pipeline name, and a list of stages."""
        store = PipelineStore()
        run = store.create_run(pipeline_name, config, stages)
        run.status = pipeline_status

        response = _serialize_run(run)

        # Must include overall PipelineStatus
        assert "status" in response, "Response missing 'status' field"
        assert response["status"] == pipeline_status.value, (
            f"Expected status={pipeline_status.value!r}, got {response['status']!r}"
        )

        # Must include pipeline name
        assert "pipeline_name" in response, "Response missing 'pipeline_name' field"
        assert response["pipeline_name"] == pipeline_name, (
            f"Expected pipeline_name={pipeline_name!r}, got {response['pipeline_name']!r}"
        )

        # Must include a list of stages
        assert "stages" in response, "Response missing 'stages' field"
        assert isinstance(response["stages"], list), "stages should be a list"
        assert len(response["stages"]) == len(stages), (
            f"Expected {len(stages)} stages, got {len(response['stages'])}"
        )

    @settings(max_examples=100)
    @given(
        pipeline_name=pipeline_name_strategy,
        stages=stage_list_strategy,
        config=run_config_strategy,
        terminal_status=st.sampled_from(_TERMINAL_STAGE_STATUSES),
        operation=st.sampled_from(_ALL_OPERATIONS),
        data=st.data(),
    )
    def test_terminal_stages_include_environment_operation_and_status(
        self,
        pipeline_name: str,
        stages: list[str],
        config: RunConfig,
        terminal_status: StageStatus,
        operation: StageOperation,
        data: st.DataObject,
    ):
        """For each stage in a terminal state, the response SHALL include the
        environment name, operation type, and final status."""
        assume(len(stages) >= 1)

        store = PipelineStore()
        run = store.create_run(pipeline_name, config, stages)
        run.status = PipelineStatus.COMPLETED

        # Pick a random stage index to put in terminal state
        stage_idx = data.draw(st.integers(min_value=0, max_value=len(run.stages) - 1))
        target_stage = run.stages[stage_idx]
        target_stage.status = terminal_status
        target_stage.operation = operation
        target_stage.completed_at = datetime.utcnow()

        # For non-SKIPPED terminal stages, add a result
        if terminal_status not in (StageStatus.SKIPPED, StageStatus.CANCELLED):
            target_stage.result = StageResult(
                environment=target_stage.environment,
                operation=operation,
                deployment_uuid="test-uuid-123",
                status=terminal_status.value,
            )

        response = _serialize_run(run)

        # Find the serialized stage
        serialized_stage = response["stages"][stage_idx]

        # Must include environment name
        assert "environment" in serialized_stage, "Stage missing 'environment' field"
        assert serialized_stage["environment"] == target_stage.environment

        # Must include operation type
        assert "operation" in serialized_stage, "Stage missing 'operation' field"
        assert serialized_stage["operation"] == operation.value

        # Must include final status
        assert "status" in serialized_stage, "Stage missing 'status' field"
        assert serialized_stage["status"] == terminal_status.value

        # If stage has a result, verify result includes environment, operation, status
        if target_stage.result is not None:
            assert "result" in serialized_stage, (
                "Terminal stage with result missing 'result' field"
            )
            result_dict = serialized_stage["result"]
            assert "environment" in result_dict, "Result missing 'environment' field"
            assert result_dict["environment"] == target_stage.environment
            assert "operation" in result_dict, "Result missing 'operation' field"
            assert result_dict["operation"] == operation.value
            assert "status" in result_dict, "Result missing 'status' field"
            assert result_dict["status"] == terminal_status.value

    @settings(max_examples=100)
    @given(
        pipeline_name=pipeline_name_strategy,
        stages=stage_list_strategy,
        config=run_config_strategy,
        data=st.data(),
    )
    def test_awaiting_approval_includes_pending_environment(
        self,
        pipeline_name: str,
        stages: list[str],
        config: RunConfig,
        data: st.DataObject,
    ):
        """When the run is in AWAITING_APPROVAL, the response SHALL additionally
        include the pending environment name."""
        # Need at least 2 stages (source + at least one target)
        assume(len(stages) >= 2)

        store = PipelineStore()
        run = store.create_run(pipeline_name, config, stages)
        run.status = PipelineStatus.AWAITING_APPROVAL

        # Mark the first stage as completed (export done)
        run.stages[0].status = StageStatus.COMPLETED
        run.stages[0].operation = StageOperation.EXPORT
        run.stages[0].completed_at = datetime.utcnow()
        run.stages[0].result = StageResult(
            environment=stages[0],
            operation=StageOperation.EXPORT,
            deployment_uuid="export-uuid",
            status="COMPLETED",
        )

        # Pick a target stage (index 1+) to be the pending approval stage
        pending_idx = data.draw(st.integers(min_value=1, max_value=len(stages) - 1))

        # Mark stages before pending_idx as completed
        for i in range(1, pending_idx):
            run.stages[i].status = StageStatus.COMPLETED
            run.stages[i].operation = StageOperation.IMPORT
            run.stages[i].completed_at = datetime.utcnow()
            run.stages[i].result = StageResult(
                environment=stages[i],
                operation=StageOperation.IMPORT,
                deployment_uuid=f"import-uuid-{i}",
                status="COMPLETED",
            )

        # The pending stage should be in INSPECTING or PENDING state
        # (inspection done, waiting for approval before import)
        run.stages[pending_idx].status = StageStatus.PENDING
        run.stages[pending_idx].operation = StageOperation.INSPECT
        run.stages[pending_idx].result = StageResult(
            environment=stages[pending_idx],
            operation=StageOperation.INSPECT,
            deployment_uuid="inspect-uuid",
            status="COMPLETED",
            errors=[],
            warnings=[],
            object_counts={"expected": 10, "failed": 0, "skipped": 0},
        )

        response = _serialize_run(run)

        # Verify the response is in AWAITING_APPROVAL status
        assert response["status"] == PipelineStatus.AWAITING_APPROVAL.value

        # The response must include the stages list with the pending environment
        # identifiable. The pending environment is the one at pending_idx.
        pending_stage_response = response["stages"][pending_idx]
        assert pending_stage_response["environment"] == stages[pending_idx], (
            f"Expected pending environment={stages[pending_idx]!r}, "
            f"got {pending_stage_response['environment']!r}"
        )

        # The pending stage should have an inspection result with the environment
        assert "result" in pending_stage_response, (
            "AWAITING_APPROVAL stage should include inspection result"
        )
        result = pending_stage_response["result"]
        assert result["environment"] == stages[pending_idx], (
            "Inspection result should include the pending environment name"
        )

        # Req 4.4: Response must include explicit pending_approval_environment
        assert "pending_approval_environment" in response, (
            "AWAITING_APPROVAL response missing 'pending_approval_environment' field"
        )
        assert response["pending_approval_environment"] == stages[pending_idx], (
            f"Expected pending_approval_environment={stages[pending_idx]!r}, "
            f"got {response['pending_approval_environment']!r}"
        )

        # Req 4.4: Response must include inspection_summary
        assert "inspection_summary" in response, (
            "AWAITING_APPROVAL response missing 'inspection_summary' field"
        )
        summary = response["inspection_summary"]
        assert summary is not None, "inspection_summary should not be None"
        assert summary["environment"] == stages[pending_idx]
        assert "total_errors" in summary
        assert "total_warnings" in summary
        assert "errors" in summary
        assert "warnings" in summary
        assert "object_counts" in summary

    @settings(max_examples=100)
    @given(
        pipeline_name=pipeline_name_strategy,
        stages=stage_list_strategy,
        config=run_config_strategy,
    )
    def test_status_response_stages_preserve_order(
        self,
        pipeline_name: str,
        stages: list[str],
        config: RunConfig,
    ):
        """The stages list in the response SHALL preserve the original order."""
        store = PipelineStore()
        run = store.create_run(pipeline_name, config, stages)
        run.status = PipelineStatus.IN_PROGRESS

        response = _serialize_run(run)

        # Verify stage order matches
        for i, (expected_env, stage_response) in enumerate(
            zip(stages, response["stages"])
        ):
            assert stage_response["environment"] == expected_env, (
                f"Stage {i}: expected environment={expected_env!r}, "
                f"got {stage_response['environment']!r}"
            )
            assert stage_response["stage_number"] == i + 1, (
                f"Stage {i}: expected stage_number={i + 1}, "
                f"got {stage_response['stage_number']}"
            )

    @settings(max_examples=100)
    @given(
        pipeline_name=pipeline_name_strategy,
        stages=stage_list_strategy,
        config=run_config_strategy,
        pipeline_status=st.sampled_from(_ALL_PIPELINE_STATUSES),
    )
    def test_status_response_includes_run_id(
        self,
        pipeline_name: str,
        stages: list[str],
        config: RunConfig,
        pipeline_status: PipelineStatus,
    ):
        """The status response SHALL include the run_id for identification."""
        store = PipelineStore()
        run = store.create_run(pipeline_name, config, stages)
        run.status = pipeline_status

        response = _serialize_run(run)

        assert "run_id" in response, "Response missing 'run_id' field"
        assert response["run_id"] == run.run_id

    @settings(max_examples=100)
    @given(
        pipeline_name=pipeline_name_strategy,
        stages=stage_list_strategy,
        config=run_config_strategy,
        data=st.data(),
    )
    def test_awaiting_approval_inspection_summary_present(
        self,
        pipeline_name: str,
        stages: list[str],
        config: RunConfig,
        data: st.DataObject,
    ):
        """When the run is in AWAITING_APPROVAL, the inspection summary (errors,
        warnings, object_counts) from the pending environment SHALL be included."""
        assume(len(stages) >= 2)

        store = PipelineStore()
        run = store.create_run(pipeline_name, config, stages)
        run.status = PipelineStatus.AWAITING_APPROVAL

        # Mark first stage as completed export
        run.stages[0].status = StageStatus.COMPLETED
        run.stages[0].operation = StageOperation.EXPORT
        run.stages[0].completed_at = datetime.utcnow()
        run.stages[0].result = StageResult(
            environment=stages[0],
            operation=StageOperation.EXPORT,
            deployment_uuid="export-uuid",
            status="COMPLETED",
        )

        # Generate inspection results for the pending stage
        errors = data.draw(st.lists(
            st.fixed_dictionaries({"message": st.text(min_size=1, max_size=20)}),
            max_size=5,
        ))
        warnings = data.draw(st.lists(
            st.fixed_dictionaries({"message": st.text(min_size=1, max_size=20)}),
            max_size=5,
        ))
        object_counts = data.draw(st.fixed_dictionaries({
            "expected": st.integers(0, 100),
            "failed": st.integers(0, 10),
            "skipped": st.integers(0, 10),
        }))

        # The second stage is awaiting approval with inspection result
        pending_stage = run.stages[1]
        pending_stage.status = StageStatus.PENDING
        pending_stage.operation = StageOperation.INSPECT
        pending_stage.result = StageResult(
            environment=stages[1],
            operation=StageOperation.INSPECT,
            deployment_uuid="inspect-uuid",
            status="COMPLETED",
            errors=errors,
            warnings=warnings,
            object_counts=object_counts,
        )

        response = _serialize_run(run)

        # The pending stage's result should include the inspection summary
        pending_response = response["stages"][1]
        assert "result" in pending_response, (
            "Pending approval stage should include inspection result"
        )
        result = pending_response["result"]
        assert result["errors"] == errors, "Inspection errors not preserved"
        assert result["warnings"] == warnings, "Inspection warnings not preserved"
        assert result["object_counts"] == object_counts, "Object counts not preserved"
        assert result["environment"] == stages[1], (
            "Inspection result should include the pending environment name"
        )

        # Req 4.4: Top-level inspection_summary must match the stage's inspection data
        assert "inspection_summary" in response, (
            "AWAITING_APPROVAL response missing 'inspection_summary' field"
        )
        summary = response["inspection_summary"]
        assert summary is not None
        assert summary["environment"] == stages[1]
        assert summary["errors"] == errors
        assert summary["warnings"] == warnings
        assert summary["total_errors"] == len(errors)
        assert summary["total_warnings"] == len(warnings)
        assert summary["object_counts"] == object_counts
