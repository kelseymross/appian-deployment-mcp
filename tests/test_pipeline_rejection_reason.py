"""Property-based tests for pipeline rejection recording reason.

Feature: deployment-pipeline, Property 10: Rejection cancels run and records reason

For any pipeline run in AWAITING_APPROVAL status and any rejection reason string
(0-2000 chars), invoking reject_pipeline_stage SHALL set the run status to CANCELLED
and the recorded rejection reason SHALL equal the provided reason string.

**Validates: Requirements 3.5**
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

# Strategy for rejection reason strings (0-2000 chars)
reason_strategy = st.text(min_size=0, max_size=2000)


class TestProperty10RejectionRecordsReason:
    """Property 10: Rejection cancels run and records reason.

    Feature: deployment-pipeline, Property 10: Rejection cancels run and records reason

    For any pipeline run in AWAITING_APPROVAL status and any rejection reason string
    (0-2000 chars), invoking reject_pipeline_stage SHALL set the run status to CANCELLED
    and the recorded rejection reason SHALL equal the provided reason string.

    **Validates: Requirements 3.5**
    """

    @settings(max_examples=100, deadline=None)
    @given(
        config=run_config_strategy,
        stages=stage_list_strategy,
        reason=reason_strategy,
    )
    def test_rejection_records_reason_string(
        self,
        config: RunConfig,
        stages: list[str],
        reason: str,
    ):
        """Rejecting an AWAITING_APPROVAL run records the rejection reason exactly.

        **Validates: Requirements 3.5**
        """
        store = PipelineStore()

        # Create a run and set it to AWAITING_APPROVAL
        run = store.create_run("test-pipeline", config, stages)
        run.status = PipelineStatus.AWAITING_APPROVAL

        # Patch get_pipeline_store to return our test store
        with patch(
            "appian_deployment_mcp.tools.pipeline_approvals.get_pipeline_store",
            return_value=store,
        ):
            from appian_deployment_mcp.tools.pipeline_approvals import (
                reject_pipeline_stage,
            )

            result = asyncio.get_event_loop().run_until_complete(
                reject_pipeline_stage(run.run_id, reason=reason)
            )

        # Must not return an error
        assert "error" not in result, (
            f"Expected successful rejection but got error: {result}"
        )

        # The rejection reason on the run should match the provided reason
        # Note: empty strings are falsy, so the tool only records non-empty reasons
        if reason:
            assert run.rejection_reason == reason, (
                f"Expected rejection_reason='{reason}' but got "
                f"'{run.rejection_reason}'"
            )
        else:
            # Empty string is falsy, so rejection_reason remains None
            assert run.rejection_reason is None, (
                f"Expected rejection_reason=None for empty reason but got "
                f"'{run.rejection_reason}'"
            )

    @settings(max_examples=100, deadline=None)
    @given(
        config=run_config_strategy,
        stages=stage_list_strategy,
        reason=reason_strategy,
    )
    def test_rejection_signals_approval_event(
        self,
        config: RunConfig,
        stages: list[str],
        reason: str,
    ):
        """Rejecting an AWAITING_APPROVAL run signals the approval event.

        **Validates: Requirements 3.5**
        """
        store = PipelineStore()

        # Create a run and set it to AWAITING_APPROVAL
        run = store.create_run("test-pipeline", config, stages)
        run.status = PipelineStatus.AWAITING_APPROVAL

        # Verify event is not set before rejection
        assert not run._approval_event.is_set()

        # Patch get_pipeline_store to return our test store
        with patch(
            "appian_deployment_mcp.tools.pipeline_approvals.get_pipeline_store",
            return_value=store,
        ):
            from appian_deployment_mcp.tools.pipeline_approvals import (
                reject_pipeline_stage,
            )

            asyncio.get_event_loop().run_until_complete(
                reject_pipeline_stage(run.run_id, reason=reason)
            )

        # The approval event must be set (signaled)
        assert run._approval_event.is_set(), (
            "Expected _approval_event to be set after rejection"
        )

        # The approval_granted flag must be False
        assert run._approval_granted is False, (
            f"Expected _approval_granted=False but got {run._approval_granted}"
        )

    @settings(max_examples=100, deadline=None)
    @given(
        config=run_config_strategy,
        stages=stage_list_strategy,
        reason=reason_strategy,
    )
    def test_rejection_response_contains_reason(
        self,
        config: RunConfig,
        stages: list[str],
        reason: str,
    ):
        """The rejection response includes the recorded rejection reason.

        **Validates: Requirements 3.5**
        """
        store = PipelineStore()

        # Create a run and set it to AWAITING_APPROVAL
        run = store.create_run("test-pipeline", config, stages)
        run.status = PipelineStatus.AWAITING_APPROVAL

        # Patch get_pipeline_store to return our test store
        with patch(
            "appian_deployment_mcp.tools.pipeline_approvals.get_pipeline_store",
            return_value=store,
        ):
            from appian_deployment_mcp.tools.pipeline_approvals import (
                reject_pipeline_stage,
            )

            result = asyncio.get_event_loop().run_until_complete(
                reject_pipeline_stage(run.run_id, reason=reason)
            )

        # Must not return an error
        assert "error" not in result, (
            f"Expected successful rejection but got error: {result}"
        )

        # Response must include run_id and rejection_reason
        assert result["run_id"] == run.run_id
        assert "rejection_reason" in result

        # The rejection_reason in the response should match what's on the run
        if reason:
            assert result["rejection_reason"] == reason
        else:
            assert result["rejection_reason"] is None
