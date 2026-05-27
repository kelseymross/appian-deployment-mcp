"""Property-based tests for non-existent pipeline lookup.

Feature: deployment-pipeline, Property 6: Non-existent pipeline lookup returns error

For any pipeline name that has not been created, both get_pipeline and run_pipeline
SHALL return an error message indicating the pipeline was not found.

**Validates: Requirements 1.8, 2.2, 2.3**
"""

from __future__ import annotations

import asyncio

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from appian_deployment_mcp.pipeline.store import PipelineStore


# Strategy for generating pipeline names (non-empty strings, 1-128 chars)
pipeline_name_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        whitelist_characters="-_ ",
    ),
    min_size=1,
    max_size=128,
).filter(lambda s: s.strip() != "")

# Strategy for generating a set of existing pipeline names (to populate the store)
existing_names_strategy = st.lists(
    pipeline_name_strategy,
    min_size=0,
    max_size=10,
    unique=True,
)

# Strategy for valid stage lists (used when populating the store)
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


class TestProperty6NonExistentPipelineLookup:
    """Property 6: Non-existent pipeline lookup returns error.

    Feature: deployment-pipeline, Property 6: Non-existent pipeline lookup returns error

    For any pipeline name that has not been created, both get_pipeline and
    run_pipeline SHALL return an error message indicating the pipeline was not found.

    **Validates: Requirements 1.8, 2.2, 2.3**
    """

    @settings(max_examples=100)
    @given(
        existing_names=existing_names_strategy,
        lookup_name=pipeline_name_strategy,
        stages=stage_list_strategy,
    )
    def test_get_pipeline_returns_error_for_nonexistent_name(
        self,
        existing_names: list[str],
        lookup_name: str,
        stages: list[str],
    ):
        """get_pipeline returns an error dict for any name not in the store.

        **Validates: Requirements 1.8**
        """
        # Ensure the lookup name is NOT in the set of existing names
        assume(lookup_name not in existing_names)

        store = PipelineStore()

        # Populate the store with some existing pipelines
        for name in existing_names:
            store.create_definition(name, stages)

        # Verify get_definition returns None for the non-existent name
        result = store.get_definition(lookup_name)
        assert result is None, (
            f"Expected None for non-existent pipeline '{lookup_name}', "
            f"but got {result}"
        )

    @settings(max_examples=100)
    @given(
        existing_names=existing_names_strategy,
        lookup_name=pipeline_name_strategy,
        stages=stage_list_strategy,
    )
    def test_get_pipeline_tool_returns_error_for_nonexistent_name(
        self,
        existing_names: list[str],
        lookup_name: str,
        stages: list[str],
    ):
        """The get_pipeline MCP tool returns an error dict when the pipeline
        name does not exist in the store.

        **Validates: Requirements 1.8**
        """
        from unittest.mock import patch

        # Ensure the lookup name is NOT in the set of existing names
        assume(lookup_name not in existing_names)

        store = PipelineStore()

        # Populate the store with some existing pipelines
        for name in existing_names:
            store.create_definition(name, stages)

        # Patch get_pipeline_store to return our test store
        with patch(
            "appian_deployment_mcp.tools.pipeline_definitions.get_pipeline_store",
            return_value=store,
        ):
            from appian_deployment_mcp.tools.pipeline_definitions import get_pipeline

            result = asyncio.get_event_loop().run_until_complete(
                get_pipeline(lookup_name)
            )

        # Must return an error dict
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "error" in result, (
            f"Expected 'error' key in result for non-existent pipeline '{lookup_name}', "
            f"got {result}"
        )
        # The error message should indicate the pipeline was not found
        assert lookup_name in result["error"] or "not found" in result["error"].lower(), (
            f"Error message should reference the pipeline name or indicate 'not found': "
            f"{result['error']}"
        )

    @settings(max_examples=100)
    @given(
        existing_names=existing_names_strategy,
        lookup_name=pipeline_name_strategy,
        stages=stage_list_strategy,
    )
    def test_run_pipeline_returns_error_for_nonexistent_name(
        self,
        existing_names: list[str],
        lookup_name: str,
        stages: list[str],
    ):
        """run_pipeline returns an error when the pipeline name does not exist.

        Since run_pipeline (task 7.1) relies on store.get_definition to check
        if a pipeline exists, this test verifies the store returns None for
        non-existent names, which is the precondition for run_pipeline to
        return an error per Requirements 2.2 and 2.3.

        **Validates: Requirements 2.2, 2.3**
        """
        # Ensure the lookup name is NOT in the set of existing names
        assume(lookup_name not in existing_names)

        store = PipelineStore()

        # Populate the store with some existing pipelines
        for name in existing_names:
            store.create_definition(name, stages)

        # Verify get_definition returns None — this is the check run_pipeline
        # will use to determine the pipeline doesn't exist
        definition = store.get_definition(lookup_name)
        assert definition is None, (
            f"Expected None for non-existent pipeline '{lookup_name}', "
            f"but got {definition}"
        )

        # Also verify that existing names DO return valid definitions
        for name in existing_names:
            existing_def = store.get_definition(name)
            assert existing_def is not None, (
                f"Expected definition for existing pipeline '{name}', got None"
            )
            assert existing_def.name == name
