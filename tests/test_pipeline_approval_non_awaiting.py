"""Property-based tests for approval/rejection of non-awaiting pipeline runs.

Feature: deployment-pipeline, Property 9: Approval/rejection of non-awaiting run returns error

For any pipeline run whose status is not AWAITING_APPROVAL, invoking
approve_pipeline_stage or reject_pipeline_stage SHALL return an error message
that includes the current status of the run.

**Validates: Requirements 3.3, 3.6**
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from hypothesis import given, settings
from hypothesis import strategies as st

from appian_deployment_mcp.pipeline.models import (
    PipelineStatus,
    RunConfig,
)
from appian_deployment_mcp.pipeline.store import PipelineStore


# Non-AWAITING_APPROVAL statuses
NON_AWAITING_STATUSES = [
    PipelineStatus.PENDING,
    PipelineStatus.IN_PROGRESS,
    PipelineStatus.COMPLETED,
    PipelineStatus.FAILED,
    PipelineStatus.CANCELLED,
]

# Strategy for generating valid stage lists
stage_list_strategy = st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
        min_size=1,
        max_size=20,
    ),
    min_size=1,
    max_size=5,
    unique=True,
)

# Strategy for generating a valid RunConfig
run_config_strategy = st.builds(
    RunConfig,
    uuids=st.lists(st.uuids().map(str), min_size=1, max_size=5),
    export_type=st.sampled_from(["package", "application"]),
    export_name=st.text(min_size=1, max_size=50),
)

# Strategy for optional comment/reason strings
comment_strategy = st.one_of(
    st.none(),
    st.text(min_size=0, max_size=2000),
)


class TestProperty9ApprovalOfNonAwaitingRunReturnsError:
    """Property 9: Approval/rejection of non-awaiting run returns error.

    Feature: deployment-pipeline, Property 9: Approval/rejection of non-awaiting run returns error

    For any pipeline run whose status is not AWAITING_APPROVAL, invoking
    approve_pipeline_stage or reject_pipeline_stage SHALL return an error
    message that includes the current status of the run.

    **Validates: Requirements 3.3, 3.6**
    """

    @settings(max_examples=100, deadline=None)
    @given(
        status=st.sampled_from(NON_AWAITING_STATUSES),
        config=run_config_strategy,
        stages=stage_list_strategy,
        comment=comment_strategy,
    )
    def test_approve_non_awaiting_run_returns_error_with_status(
        self,
        status: PipelineStatus,
        config: RunConfig,
        stages: list[str],
        comment: str | None,
    ):
        """Approving a run not in AWAITING_APPROVAL returns error containing current status.

        **Validates: Requirements 3.3**
        """
        store = PipelineStore()

        # Create a run and set it to a non-AWAITING_APPROVAL status
        run = store.create_run("test-pipeline", config, stages)
        run.status = status

        with patch(
            "appian_deployment_mcp.tools.pipeline_approvals.get_pipeline_store",
            return_value=store,
        ):
            from appian_deployment_mcp.tools.pipeline_approvals import approve_pipeline_stage

            result = asyncio.get_event_loop().run_until_complete(
                approve_pipeline_stage(run.run_id, comment=comment)
            )

        # Must return an error dict
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "error" in result, (
            f"Expected 'error' key in result for run with status "
            f"'{status.value}', got {result}"
        )
        # The error message must include the current status
        assert status.value in result["error"], (
            f"Error message should contain the current status "
            f"'{status.value}': {result['error']}"
        )

    @settings(max_examples=100, deadline=None)
    @given(
        status=st.sampled_from(NON_AWAITING_STATUSES),
        config=run_config_strategy,
        stages=stage_list_strategy,
        reason=comment_strategy,
    )
    def test_reject_non_awaiting_run_returns_error_with_status(
        self,
        status: PipelineStatus,
        config: RunConfig,
        stages: list[str],
        reason: str | None,
    ):
        """Rejecting a run not in AWAITING_APPROVAL returns error containing current status.

        **Validates: Requirements 3.6**
        """
        store = PipelineStore()

        # Create a run and set it to a non-AWAITING_APPROVAL status
        run = store.create_run("test-pipeline", config, stages)
        run.status = status

        with patch(
            "appian_deployment_mcp.tools.pipeline_approvals.get_pipeline_store",
            return_value=store,
        ):
            from appian_deployment_mcp.tools.pipeline_approvals import reject_pipeline_stage

            result = asyncio.get_event_loop().run_until_complete(
                reject_pipeline_stage(run.run_id, reason=reason)
            )

        # Must return an error dict
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "error" in result, (
            f"Expected 'error' key in result for run with status "
            f"'{status.value}', got {result}"
        )
        # The error message must include the current status
        assert status.value in result["error"], (
            f"Error message should contain the current status "
            f"'{status.value}': {result['error']}"
        )

    @settings(max_examples=100, deadline=None)
    @given(
        status=st.sampled_from(NON_AWAITING_STATUSES),
        config=run_config_strategy,
        stages=stage_list_strategy,
    )
    def test_approve_non_awaiting_run_does_not_change_status(
        self,
        status: PipelineStatus,
        config: RunConfig,
        stages: list[str],
    ):
        """Approving a non-awaiting run does not modify the run's status.

        **Validates: Requirements 3.3**
        """
        store = PipelineStore()

        # Create a run and set it to a non-AWAITING_APPROVAL status
        run = store.create_run("test-pipeline", config, stages)
        run.status = status

        with patch(
            "appian_deployment_mcp.tools.pipeline_approvals.get_pipeline_store",
            return_value=store,
        ):
            from appian_deployment_mcp.tools.pipeline_approvals import approve_pipeline_stage

            asyncio.get_event_loop().run_until_complete(
                approve_pipeline_stage(run.run_id, comment="should not work")
            )

        # The run's status should remain unchanged
        assert run.status == status, (
            f"Expected status to remain '{status.value}' but got "
            f"'{run.status.value}'"
        )

    @settings(max_examples=100, deadline=None)
    @given(
        status=st.sampled_from(NON_AWAITING_STATUSES),
        config=run_config_strategy,
        stages=stage_list_strategy,
    )
    def test_reject_non_awaiting_run_does_not_change_status(
        self,
        status: PipelineStatus,
        config: RunConfig,
        stages: list[str],
    ):
        """Rejecting a non-awaiting run does not modify the run's status.

        **Validates: Requirements 3.6**
        """
        store = PipelineStore()

        # Create a run and set it to a non-AWAITING_APPROVAL status
        run = store.create_run("test-pipeline", config, stages)
        run.status = status

        with patch(
            "appian_deployment_mcp.tools.pipeline_approvals.get_pipeline_store",
            return_value=store,
        ):
            from appian_deployment_mcp.tools.pipeline_approvals import reject_pipeline_stage

            asyncio.get_event_loop().run_until_complete(
                reject_pipeline_stage(run.run_id, reason="should not work")
            )

        # The run's status should remain unchanged
        assert run.status == status, (
            f"Expected status to remain '{status.value}' but got "
            f"'{run.status.value}'"
        )

    @settings(max_examples=100, deadline=None)
    @given(
        status=st.sampled_from(NON_AWAITING_STATUSES),
        config=run_config_strategy,
        stages=stage_list_strategy,
    )
    def test_approve_non_awaiting_run_response_includes_status_field(
        self,
        status: PipelineStatus,
        config: RunConfig,
        stages: list[str],
    ):
        """The approve error response includes a 'status' field with the current status value.

        **Validates: Requirements 3.3**
        """
        store = PipelineStore()

        # Create a run and set it to a non-AWAITING_APPROVAL status
        run = store.create_run("test-pipeline", config, stages)
        run.status = status

        with patch(
            "appian_deployment_mcp.tools.pipeline_approvals.get_pipeline_store",
            return_value=store,
        ):
            from appian_deployment_mcp.tools.pipeline_approvals import approve_pipeline_stage

            result = asyncio.get_event_loop().run_until_complete(
                approve_pipeline_stage(run.run_id, comment=None)
            )

        # The response should include a status field
        assert "status" in result, (
            f"Expected 'status' key in error response, got {result}"
        )
        assert result["status"] == status.value, (
            f"Expected status='{status.value}' in response, "
            f"got '{result['status']}'"
        )

    @settings(max_examples=100, deadline=None)
    @given(
        status=st.sampled_from(NON_AWAITING_STATUSES),
        config=run_config_strategy,
        stages=stage_list_strategy,
    )
    def test_reject_non_awaiting_run_response_includes_status_field(
        self,
        status: PipelineStatus,
        config: RunConfig,
        stages: list[str],
    ):
        """The reject error response includes a 'status' field with the current status value.

        **Validates: Requirements 3.6**
        """
        store = PipelineStore()

        # Create a run and set it to a non-AWAITING_APPROVAL status
        run = store.create_run("test-pipeline", config, stages)
        run.status = status

        with patch(
            "appian_deployment_mcp.tools.pipeline_approvals.get_pipeline_store",
            return_value=store,
        ):
            from appian_deployment_mcp.tools.pipeline_approvals import reject_pipeline_stage

            result = asyncio.get_event_loop().run_until_complete(
                reject_pipeline_stage(run.run_id, reason=None)
            )

        # The response should include a status field
        assert "status" in result, (
            f"Expected 'status' key in error response, got {result}"
        )
        assert result["status"] == status.value, (
            f"Expected status='{status.value}' in response, "
            f"got '{result['status']}'"
        )
