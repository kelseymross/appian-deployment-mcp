"""Property-based tests for PipelineStore."""

from __future__ import annotations

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from appian_deployment_mcp.pipeline.models import RunConfig
from appian_deployment_mcp.pipeline.store import PipelineStore


# Strategy for generating a valid RunConfig
run_config_strategy = st.builds(
    RunConfig,
    uuids=st.lists(st.uuids().map(str), min_size=1, max_size=5),
    export_type=st.sampled_from(["package", "application"]),
    export_name=st.text(min_size=1, max_size=50),
)

# Strategy for generating valid stage lists (1-20 unique environment names)
stage_list_strategy = st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
        min_size=1,
        max_size=20,
    ),
    min_size=1,
    max_size=20,
    unique=True,
)


class TestProperty1PipelineDefinitionRoundTrip:
    """Property 1: Pipeline definition round-trip.

    Feature: deployment-pipeline, Property 1: Pipeline definition round-trip

    For any valid pipeline name (1-128 chars) and valid stage list (1-20 entries),
    creating a pipeline and then retrieving it by name SHALL return a definition
    with the same name and the same ordered stage list.

    **Validates: Requirements 1.4, 1.6**
    """

    @settings(max_examples=100)
    @given(
        name=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N", "P", "S"),
                whitelist_characters="-_ ",
            ),
            min_size=1,
            max_size=128,
        ).filter(lambda s: s.strip() != ""),
        stages=st.lists(
            st.text(
                alphabet=st.characters(
                    whitelist_categories=("L", "N"),
                    whitelist_characters="-_",
                ),
                min_size=1,
                max_size=20,
            ),
            min_size=1,
            max_size=20,
            unique=True,
        ),
    )
    def test_create_then_get_returns_same_name_and_stages(
        self, name: str, stages: list[str]
    ):
        """Create a definition then retrieve by name; verify name and stages match."""
        store = PipelineStore()

        store.create_definition(name, stages)
        result = store.get_definition(name)

        assert result is not None, f"get_definition returned None for name={name!r}"
        assert result.name == name, (
            f"Expected name={name!r} but got {result.name!r}"
        )
        assert result.stages == stages, (
            f"Expected stages={stages!r} but got {result.stages!r}"
        )


class TestRunIdUniqueness:
    """Property 17: All run IDs are unique.

    Feature: deployment-pipeline, Property 17: All run IDs are unique

    **Validates: Requirements 5.4**

    For any sequence of pipeline runs created, all assigned run_id values
    SHALL be distinct.
    """

    @settings(max_examples=100)
    @given(
        n=st.integers(min_value=2, max_value=50),
        config=run_config_strategy,
        stages=stage_list_strategy,
    )
    def test_all_run_ids_are_unique(
        self,
        n: int,
        config: RunConfig,
        stages: list[str],
    ):
        """Create N runs and verify all run_id values are distinct."""
        store = PipelineStore()

        run_ids = []
        for _ in range(n):
            run = store.create_run("test-pipeline", config, stages)
            run_ids.append(run.run_id)

        # All run IDs must be unique
        assert len(set(run_ids)) == n, (
            f"Expected {n} unique run IDs but got {len(set(run_ids))} unique values"
        )


class TestListRunsBoundedTo100:
    """Property 13: List runs bounded to 100 most recent.

    Feature: deployment-pipeline, Property 13: List runs bounded to 100 most recent

    **Validates: Requirements 4.5**
    """

    @settings(max_examples=100)
    @given(n=st.integers(min_value=101, max_value=150))
    def test_list_runs_returns_exactly_100_most_recent(self, n: int):
        """For any N > 100 pipeline runs created, list_runs returns exactly 100,
        and they are the 100 most recently created runs."""
        from datetime import datetime, timedelta

        from appian_deployment_mcp.pipeline.models import RunConfig

        store = PipelineStore()
        config = RunConfig(
            uuids=["uuid-1"],
            export_type="package",
            export_name="test-export",
        )

        # Create N runs with incrementing timestamps so ordering is deterministic
        base_time = datetime(2024, 1, 1)
        created_runs = []
        for i in range(n):
            run = store.create_run("pipeline", config, ["dev", "prod"])
            run.created_at = base_time + timedelta(seconds=i)
            created_runs.append(run)

        # list_runs with default limit should return exactly 100
        result = store.list_runs()
        assert len(result) == 100

        # The returned runs should be the 100 most recent (last 100 created)
        expected_run_ids = {r.run_id for r in created_runs[n - 100:]}
        actual_run_ids = {r.run_id for r in result}
        assert actual_run_ids == expected_run_ids

        # They should be sorted by created_at descending (most recent first)
        for i in range(len(result) - 1):
            assert result[i].created_at >= result[i + 1].created_at


# Strategy for valid pipeline names (1-128 chars)
pipeline_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S"), whitelist_characters="-_ "),
    min_size=1,
    max_size=128,
).filter(lambda s: s.strip() != "")


class TestProperty4DefinitionOverwritePreservesLatest:
    """Property 4: Pipeline definition overwrite preserves latest.

    For any pipeline name and two distinct valid stage lists, creating a pipeline
    with the first list and then creating again with the same name but the second
    list SHALL result in get_definition returning only the second stage list.

    **Validates: Requirements 1.7**
    """

    @settings(max_examples=100)
    @given(
        name=pipeline_name_strategy,
        stages1=stage_list_strategy,
        stages2=stage_list_strategy,
    )
    def test_overwrite_preserves_latest_stages(
        self, name: str, stages1: list[str], stages2: list[str]
    ):
        """Creating a definition twice with the same name returns the second stage list."""
        assume(stages1 != stages2)

        store = PipelineStore()
        store.create_definition(name, stages1)
        store.create_definition(name, stages2)

        result = store.get_definition(name)
        assert result is not None
        assert result.name == name
        assert result.stages == stages2

    @settings(max_examples=100)
    @given(
        name=pipeline_name_strategy,
        stages1=stage_list_strategy,
        stages2=stage_list_strategy,
    )
    def test_overwrite_results_in_single_definition(
        self, name: str, stages1: list[str], stages2: list[str]
    ):
        """Overwriting a definition does not create duplicates in list_definitions."""
        assume(stages1 != stages2)

        store = PipelineStore()
        store.create_definition(name, stages1)
        store.create_definition(name, stages2)

        definitions = store.list_definitions()
        names = [d.name for d in definitions]
        assert names.count(name) == 1


# Strategy: generate a list of 1-20 distinct pipeline names
distinct_names_strategy = st.lists(
    pipeline_name_strategy,
    min_size=1,
    max_size=20,
    unique=True,
)


class TestProperty5ListDefinitionsCompleteness:
    """Property 5: List pipelines returns all definitions.

    Feature: deployment-pipeline, Property 5: List pipelines returns all definitions

    For any set of N valid pipeline definitions (with distinct names) that are
    created, list_definitions SHALL return exactly N definitions, and the set of
    returned names SHALL equal the set of created names.

    **Validates: Requirements 1.5**
    """

    @settings(max_examples=100)
    @given(names=distinct_names_strategy, stages=stage_list_strategy)
    def test_list_definitions_returns_all_created(
        self, names: list[str], stages: list[str]
    ):
        """Create N definitions with distinct names; list_definitions returns
        exactly N items with matching names."""
        store = PipelineStore()

        # Create N definitions with distinct names
        for name in names:
            store.create_definition(name, stages)

        # list_definitions should return exactly N items
        result = store.list_definitions()
        assert len(result) == len(names), (
            f"Expected {len(names)} definitions but got {len(result)}"
        )

        # The set of returned names should equal the set of created names
        returned_names = {defn.name for defn in result}
        assert returned_names == set(names)
