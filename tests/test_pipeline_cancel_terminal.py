"""Property-based tests for cancellation of terminal pipeline runs.

Feature: deployment-pipeline, Property 15: Cancellation of terminal run returns error

For any pipeline run in a terminal status (COMPLETED, FAILED, or CANCELLED),
invoking cancel_pipeline_run SHALL return an error message that includes the
current terminal status.

**Validates: Requirements 6.3**
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


# Terminal statuses that cannot be cancelled
TERMINAL_STATUSES = [
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

# Strategy for optional cancellation reason
reason_strategy = st.one_of(
    st.none(),
    st.text(min_size=0, max_size=500),
)


class TestProperty15CancellationOfTerminalRunReturnsError:
    """Property 15: Cancellation of terminal run returns error.

    Feature: deployment-pipeline, Property 15: Cancellation of terminal run returns error

    For any pipeline run in a terminal status (COMPLETED, FAILED, or CANCELLED),
    invoking cancel_pipeline_run SHALL return an error message that includes the
    current terminal status.

    **Validates: Requirements 6.3**
    """

    @settings(max_examples=100, deadline=None)
    @given(
        terminal_status=st.sampled_from(TERMINAL_STATUSES),
        config=run_config_strategy,
        stages=stage_list_strategy,
        reason=reason_strategy,
    )
    def test_cancel_terminal_run_returns_error_with_status(
        self,
        terminal_status: PipelineStatus,
        config: RunConfig,
        stages: list[str],
        reason: str | None,
    ):
        """Cancelling a run in a terminal state returns an error containing the status.

        **Validates: Requirements 6.3**
        """
        store = PipelineStore()

        # Create a run and set it to a terminal status
        run = store.create_run("test-pipeline", config, stages)
        run.status = terminal_status

        # Patch get_pipeline_store to return our test store
        with patch(
            "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_store",
            return_value=store,
        ):
            from appian_deployment_mcp.tools.pipeline_runs import cancel_pipeline_run

            result = asyncio.get_event_loop().run_until_complete(
                cancel_pipeline_run(run.run_id, reason=reason)
            )

        # Must return an error dict
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "error" in result, (
            f"Expected 'error' key in result for terminal run with status "
            f"'{terminal_status.value}', got {result}"
        )
        # The error message must include the current terminal status
        assert terminal_status.value in result["error"], (
            f"Error message should contain the terminal status "
            f"'{terminal_status.value}': {result['error']}"
        )

    @settings(max_examples=100, deadline=None)
    @given(
        terminal_status=st.sampled_from(TERMINAL_STATUSES),
        config=run_config_strategy,
        stages=stage_list_strategy,
    )
    def test_cancel_terminal_run_does_not_change_status(
        self,
        terminal_status: PipelineStatus,
        config: RunConfig,
        stages: list[str],
    ):
        """Cancelling a terminal run does not modify the run's status.

        **Validates: Requirements 6.3**
        """
        store = PipelineStore()

        # Create a run and set it to a terminal status
        run = store.create_run("test-pipeline", config, stages)
        run.status = terminal_status

        # Patch get_pipeline_store to return our test store
        with patch(
            "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_store",
            return_value=store,
        ):
            from appian_deployment_mcp.tools.pipeline_runs import cancel_pipeline_run

            asyncio.get_event_loop().run_until_complete(
                cancel_pipeline_run(run.run_id, reason="should not work")
            )

        # The run's status should remain unchanged
        assert run.status == terminal_status, (
            f"Expected status to remain '{terminal_status.value}' but got "
            f"'{run.status.value}'"
        )

    @settings(max_examples=100, deadline=None)
    @given(
        terminal_status=st.sampled_from(TERMINAL_STATUSES),
        config=run_config_strategy,
        stages=stage_list_strategy,
    )
    def test_cancel_terminal_run_response_includes_status_field(
        self,
        terminal_status: PipelineStatus,
        config: RunConfig,
        stages: list[str],
    ):
        """The error response includes a 'status' field with the terminal status value.

        **Validates: Requirements 6.3**
        """
        store = PipelineStore()

        # Create a run and set it to a terminal status
        run = store.create_run("test-pipeline", config, stages)
        run.status = terminal_status

        # Patch get_pipeline_store to return our test store
        with patch(
            "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_store",
            return_value=store,
        ):
            from appian_deployment_mcp.tools.pipeline_runs import cancel_pipeline_run

            result = asyncio.get_event_loop().run_until_complete(
                cancel_pipeline_run(run.run_id, reason=None)
            )

        # The response should include a status field
        assert "status" in result, (
            f"Expected 'status' key in error response, got {result}"
        )
        assert result["status"] == terminal_status.value, (
            f"Expected status='{terminal_status.value}' in response, "
            f"got '{result['status']}'"
        )
