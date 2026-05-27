"""Property-based tests for pipeline data model construction.

Feature: deployment-pipeline, Property 1: Pipeline definition round-trip
"""

from datetime import datetime

from hypothesis import given, settings, strategies as st

from appian_deployment_mcp.pipeline.models import PipelineDefinition


# Strategy: valid pipeline names (1-128 printable characters, no leading/trailing whitespace)
pipeline_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S"), whitelist_characters="-_ "),
    min_size=1,
    max_size=128,
).filter(lambda s: s.strip() == s and len(s) >= 1)

# Strategy: valid stage lists (1-20 unique environment name strings)
stage_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=64,
)

stage_lists = st.lists(stage_names, min_size=1, max_size=20, unique=True)


class TestPipelineDefinitionRoundTrip:
    """Property 1: Pipeline definition round-trip.

    **Validates: Requirements 1.4, 1.6**

    For any valid pipeline name (1-128 chars) and valid stage list (1-20 entries),
    constructing a PipelineDefinition preserves all field values.
    """

    @given(name=pipeline_names, stages=stage_lists)
    @settings(max_examples=100)
    def test_construction_preserves_name_and_stages(self, name: str, stages: list[str]) -> None:
        """Dataclass construction preserves the name and stages fields exactly."""
        definition = PipelineDefinition(name=name, stages=stages)

        assert definition.name == name
        assert definition.stages == stages

    @given(name=pipeline_names, stages=stage_lists)
    @settings(max_examples=100)
    def test_construction_assigns_created_at(self, name: str, stages: list[str]) -> None:
        """Dataclass construction assigns a datetime to created_at."""
        before = datetime.utcnow()
        definition = PipelineDefinition(name=name, stages=stages)
        after = datetime.utcnow()

        assert isinstance(definition.created_at, datetime)
        assert before <= definition.created_at <= after

    @given(name=pipeline_names, stages=stage_lists)
    @settings(max_examples=100)
    def test_frozen_dataclass_is_hashable(self, name: str, stages: list[str]) -> None:
        """PipelineDefinition is frozen and hashable (supports use as dict key/set member)."""
        definition = PipelineDefinition(name=name, stages=stages)

        # Should not raise
        hash(definition)
