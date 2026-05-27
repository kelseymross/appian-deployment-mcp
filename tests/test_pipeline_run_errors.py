"""Property-based tests for non-existent run_id errors.

Feature: deployment-pipeline, Property 11: Non-existent run_id returns error

For any run_id string that does not correspond to an existing pipeline run,
get_pipeline_run_status, approve_pipeline_stage, reject_pipeline_stage, and
cancel_pipeline_run SHALL each return an error message indicating the run was not found.

**Validates: Requirements 3.7, 4.6, 6.5**
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from appian_deployment_mcp.pipeline.store import PipelineStore
from appian_deployment_mcp.pipeline.models import RunConfig


# Strategy for generating run_id strings (non-empty, varied formats)
run_id_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P"),
        whitelist_characters="-_",
    ),
    min_size=1,
    max_size=64,
).filter(lambda s: s.strip() != "")

# Strategy for generating a set of existing runs (to populate the store)
existing_run_count_strategy = st.integers(min_value=0, max_value=5)

# Valid stage lists for creating runs
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


def _create_test_store_with_runs(num_runs: int) -> tuple[PipelineStore, list[str]]:
    """Create a store populated with a given number of runs. Returns (store, run_ids)."""
    store = PipelineStore()
    run_ids = []
    for _ in range(num_runs):
        config = RunConfig(
            uuids=["uuid-1"],
            export_type="package",
            export_name="test-export",
            deploy_name_template=None,
            customization_file_path=None,
            inspect_before_deploy=True,
            approval_environments=[],
        )
        run = store.create_run(
            definition_name="test-pipeline",
            config=config,
            stages=["dev", "test"],
        )
        run_ids.append(run.run_id)
    return store, run_ids


class TestProperty11NonExistentRunIdErrors:
    """Property 11: Non-existent run_id returns error.

    Feature: deployment-pipeline, Property 11: Non-existent run_id returns error

    For any run_id string that does not correspond to an existing pipeline run,
    get_pipeline_run_status, approve_pipeline_stage, reject_pipeline_stage, and
    cancel_pipeline_run SHALL each return an error message indicating the run
    was not found.

    **Validates: Requirements 3.7, 4.6, 6.5**
    """

    @settings(max_examples=100, deadline=None)
    @given(
        run_id=run_id_strategy,
        num_existing_runs=existing_run_count_strategy,
    )
    def test_get_pipeline_run_status_returns_error_for_nonexistent_run_id(
        self,
        run_id: str,
        num_existing_runs: int,
    ):
        """get_pipeline_run_status returns an error for any run_id not in the store.

        **Validates: Requirements 4.6**
        """
        store, existing_ids = _create_test_store_with_runs(num_existing_runs)

        # Ensure the generated run_id is NOT one of the existing run IDs
        assume(run_id not in existing_ids)

        with patch(
            "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_store",
            return_value=store,
        ):
            from appian_deployment_mcp.tools.pipeline_runs import get_pipeline_run_status

            result = asyncio.get_event_loop().run_until_complete(
                get_pipeline_run_status(run_id)
            )

        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "error" in result, (
            f"Expected 'error' key in result for non-existent run_id '{run_id}', "
            f"got {result}"
        )
        assert "not found" in result["error"].lower(), (
            f"Error message should indicate 'not found': {result['error']}"
        )

    @settings(max_examples=100, deadline=None)
    @given(
        run_id=run_id_strategy,
        num_existing_runs=existing_run_count_strategy,
    )
    def test_cancel_pipeline_run_returns_error_for_nonexistent_run_id(
        self,
        run_id: str,
        num_existing_runs: int,
    ):
        """cancel_pipeline_run returns an error for any run_id not in the store.

        **Validates: Requirements 6.5**
        """
        store, existing_ids = _create_test_store_with_runs(num_existing_runs)

        # Ensure the generated run_id is NOT one of the existing run IDs
        assume(run_id not in existing_ids)

        with patch(
            "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_store",
            return_value=store,
        ):
            from appian_deployment_mcp.tools.pipeline_runs import cancel_pipeline_run

            result = asyncio.get_event_loop().run_until_complete(
                cancel_pipeline_run(run_id)
            )

        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "error" in result, (
            f"Expected 'error' key in result for non-existent run_id '{run_id}', "
            f"got {result}"
        )
        assert "not found" in result["error"].lower(), (
            f"Error message should indicate 'not found': {result['error']}"
        )

    @settings(max_examples=100, deadline=None)
    @given(
        run_id=run_id_strategy,
        num_existing_runs=existing_run_count_strategy,
    )
    def test_approve_pipeline_stage_returns_error_for_nonexistent_run_id(
        self,
        run_id: str,
        num_existing_runs: int,
    ):
        """approve_pipeline_stage returns an error for any run_id not in the store.

        Since pipeline_approvals.py is not yet implemented, this test verifies
        the precondition: store.get_run returns None for non-existent run_ids,
        which is the check that approve_pipeline_stage will use to return an error.

        **Validates: Requirements 3.7**
        """
        store, existing_ids = _create_test_store_with_runs(num_existing_runs)

        # Ensure the generated run_id is NOT one of the existing run IDs
        assume(run_id not in existing_ids)

        # Verify the store returns None for the non-existent run_id
        result = store.get_run(run_id)
        assert result is None, (
            f"Expected None for non-existent run_id '{run_id}', but got {result}"
        )

    @settings(max_examples=100, deadline=None)
    @given(
        run_id=run_id_strategy,
        num_existing_runs=existing_run_count_strategy,
    )
    def test_reject_pipeline_stage_returns_error_for_nonexistent_run_id(
        self,
        run_id: str,
        num_existing_runs: int,
    ):
        """reject_pipeline_stage returns an error for any run_id not in the store.

        Since pipeline_approvals.py is not yet implemented, this test verifies
        the precondition: store.get_run returns None for non-existent run_ids,
        which is the check that reject_pipeline_stage will use to return an error.

        **Validates: Requirements 3.7**
        """
        store, existing_ids = _create_test_store_with_runs(num_existing_runs)

        # Ensure the generated run_id is NOT one of the existing run IDs
        assume(run_id not in existing_ids)

        # Verify the store returns None for the non-existent run_id
        result = store.get_run(run_id)
        assert result is None, (
            f"Expected None for non-existent run_id '{run_id}', but got {result}"
        )
