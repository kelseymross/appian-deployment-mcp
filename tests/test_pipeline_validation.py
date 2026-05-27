"""Unit tests and property tests for pipeline validation functions."""

from __future__ import annotations

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from appian_deployment_mcp.pipeline.validation import (
    validate_pipeline_stages,
    validate_run_params,
)


class TestValidatePipelineStages:
    """Tests for validate_pipeline_stages."""

    def test_valid_stages_returns_none(self) -> None:
        environments = {"dev": {}, "test": {}, "prod": {}}
        result = validate_pipeline_stages(["dev", "test", "prod"], environments)
        assert result is None

    def test_single_valid_stage(self) -> None:
        environments = {"dev": {}, "test": {}}
        result = validate_pipeline_stages(["dev"], environments)
        assert result is None

    def test_invalid_environment_name(self) -> None:
        environments = {"dev": {}, "test": {}}
        result = validate_pipeline_stages(["dev", "staging"], environments)
        assert result is not None
        assert "error" in result
        assert "staging" in result["error"]

    def test_multiple_invalid_environment_names(self) -> None:
        environments = {"dev": {}}
        result = validate_pipeline_stages(["dev", "staging", "prod"], environments)
        assert result is not None
        assert "staging" in result["error"]
        assert "prod" in result["error"]

    def test_duplicate_environment_names(self) -> None:
        environments = {"dev": {}, "test": {}, "prod": {}}
        result = validate_pipeline_stages(["dev", "test", "dev"], environments)
        assert result is not None
        assert "Duplicate" in result["error"]
        assert "dev" in result["error"]

    def test_both_invalid_and_duplicate(self) -> None:
        environments = {"dev": {}, "test": {}}
        result = validate_pipeline_stages(["dev", "dev", "staging"], environments)
        assert result is not None
        assert "Invalid" in result["error"]
        assert "Duplicate" in result["error"]
        assert "staging" in result["error"]
        assert "dev" in result["error"]

    def test_empty_stages_returns_none(self) -> None:
        """Empty stages list has no invalid names or duplicates."""
        environments = {"dev": {}}
        result = validate_pipeline_stages([], environments)
        assert result is None

    def test_empty_environments_all_invalid(self) -> None:
        environments: dict = {}
        result = validate_pipeline_stages(["dev", "test"], environments)
        assert result is not None
        assert "dev" in result["error"]
        assert "test" in result["error"]


class TestValidateRunParams:
    """Tests for validate_run_params."""

    def test_valid_params_returns_none(self) -> None:
        result = validate_run_params(
            uuids=["uuid-1"],
            export_type="package",
            stages=["dev", "test"],
            approval_environments=["test"],
        )
        assert result is None

    def test_valid_application_export_type(self) -> None:
        result = validate_run_params(
            uuids=["uuid-1"],
            export_type="application",
            stages=["dev", "test"],
            approval_environments=None,
        )
        assert result is None

    def test_invalid_export_type(self) -> None:
        result = validate_run_params(
            uuids=["uuid-1"],
            export_type="invalid",
            stages=["dev", "test"],
            approval_environments=None,
        )
        assert result is not None
        assert "export_type" in result["error"]
        assert "invalid" in result["error"]

    def test_empty_uuids(self) -> None:
        result = validate_run_params(
            uuids=[],
            export_type="package",
            stages=["dev", "test"],
            approval_environments=None,
        )
        assert result is not None
        assert "uuids" in result["error"]
        assert "at least 1" in result["error"]

    def test_too_many_uuids(self) -> None:
        result = validate_run_params(
            uuids=[f"uuid-{i}" for i in range(101)],
            export_type="package",
            stages=["dev", "test"],
            approval_environments=None,
        )
        assert result is not None
        assert "uuids" in result["error"]
        assert "100" in result["error"]

    def test_exactly_100_uuids_valid(self) -> None:
        result = validate_run_params(
            uuids=[f"uuid-{i}" for i in range(100)],
            export_type="package",
            stages=["dev", "test"],
            approval_environments=None,
        )
        assert result is None

    def test_stages_below_min_default(self) -> None:
        """Default min_stages is 1, so empty stages fails."""
        result = validate_run_params(
            uuids=["uuid-1"],
            export_type="package",
            stages=[],
            approval_environments=None,
        )
        assert result is not None
        assert "stages" in result["error"]

    def test_stages_below_min_adhoc(self) -> None:
        """Ad-hoc pipelines require min_stages=2."""
        result = validate_run_params(
            uuids=["uuid-1"],
            export_type="package",
            stages=["dev"],
            approval_environments=None,
            min_stages=2,
        )
        assert result is not None
        assert "stages" in result["error"]
        assert "2" in result["error"]

    def test_stages_above_max(self) -> None:
        result = validate_run_params(
            uuids=["uuid-1"],
            export_type="package",
            stages=[f"env-{i}" for i in range(21)],
            approval_environments=None,
        )
        assert result is not None
        assert "stages" in result["error"]
        assert "20" in result["error"]

    def test_exactly_20_stages_valid(self) -> None:
        result = validate_run_params(
            uuids=["uuid-1"],
            export_type="package",
            stages=[f"env-{i}" for i in range(20)],
            approval_environments=None,
        )
        assert result is None

    def test_approval_environments_not_subset(self) -> None:
        result = validate_run_params(
            uuids=["uuid-1"],
            export_type="package",
            stages=["dev", "test"],
            approval_environments=["prod"],
        )
        assert result is not None
        assert "approval_environments" in result["error"]
        assert "prod" in result["error"]

    def test_approval_environments_none_valid(self) -> None:
        result = validate_run_params(
            uuids=["uuid-1"],
            export_type="package",
            stages=["dev", "test"],
            approval_environments=None,
        )
        assert result is None

    def test_approval_environments_empty_list_valid(self) -> None:
        result = validate_run_params(
            uuids=["uuid-1"],
            export_type="package",
            stages=["dev", "test"],
            approval_environments=[],
        )
        assert result is None

    def test_multiple_errors_combined(self) -> None:
        """Multiple validation failures are combined in a single error."""
        result = validate_run_params(
            uuids=[],
            export_type="invalid",
            stages=[],
            approval_environments=None,
        )
        assert result is not None
        assert "export_type" in result["error"]
        assert "uuids" in result["error"]


# --- Hypothesis strategies for environment names ---

# Strategy for valid environment names: non-empty alphanumeric strings (1-30 chars)
env_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip() == s and len(s) > 0)


class TestPropertyDuplicateEnvironmentValidation:
    """Property 3: Pipeline definition rejects duplicate environments.

    Feature: deployment-pipeline, Property 3: Pipeline definition rejects duplicate environments

    For any stage list containing duplicate environment names,
    validate_pipeline_stages SHALL return an error whose message contains
    every duplicated name, regardless of how many times each name appears.

    **Validates: Requirements 1.9**
    """

    @settings(max_examples=100)
    @given(
        unique_names=st.lists(env_name_strategy, min_size=1, max_size=10, unique=True),
        dup_indices=st.data(),
    )
    def test_duplicate_environments_reported_in_error(
        self, unique_names: list[str], dup_indices: st.DataObject
    ) -> None:
        """Generate stage lists with duplicates; verify error message contains every duplicated name."""
        # Pick at least 1 name to duplicate
        num_to_dup = dup_indices.draw(
            st.integers(min_value=1, max_value=len(unique_names))
        )
        names_to_duplicate = unique_names[:num_to_dup]

        # Build a stage list: all unique names + duplicates of selected names
        # Each duplicated name appears at least twice
        extra_copies = []
        for name in names_to_duplicate:
            repeat_count = dup_indices.draw(st.integers(min_value=1, max_value=3))
            extra_copies.extend([name] * repeat_count)

        stages = unique_names + extra_copies

        # All names are "valid" environments (present in the environments dict)
        environments = {name: {} for name in unique_names}

        result = validate_pipeline_stages(stages, environments)

        # Must return an error since there are duplicates
        assert result is not None, (
            f"Expected error for duplicates {names_to_duplicate}, got None"
        )
        assert "error" in result

        # Every duplicated name must appear in the error message
        error_msg = result["error"]
        for dup_name in names_to_duplicate:
            assert dup_name in error_msg, (
                f"Duplicated name '{dup_name}' not found in error: {error_msg}"
            )


# --- Property-Based Tests ---

# Strategy for generating valid environment names
_env_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=20,
)


class TestProperty2InvalidEnvironmentValidation:
    """Property 2: Pipeline definition rejects invalid environments.

    Feature: deployment-pipeline, Property 2: Pipeline definition rejects invalid environments

    For any stage list containing one or more environment names that do not
    correspond to configured environments, validate_pipeline_stages SHALL return
    an error whose message contains every invalid environment name from the input.

    **Validates: Requirements 1.2, 1.3, 5.3**
    """

    @settings(max_examples=100)
    @given(
        valid_envs=st.lists(
            _env_name_strategy,
            min_size=1,
            max_size=10,
            unique=True,
        ),
        invalid_envs=st.lists(
            _env_name_strategy,
            min_size=1,
            max_size=10,
            unique=True,
        ),
    )
    def test_error_contains_every_invalid_name(
        self, valid_envs: list[str], invalid_envs: list[str]
    ):
        """Generate stage lists with invalid names; verify error message
        contains every invalid name."""
        # Ensure invalid_envs are truly not in the configured environments
        environments = {name: {} for name in valid_envs}
        actual_invalid = [name for name in invalid_envs if name not in environments]
        assume(len(actual_invalid) >= 1)

        # Build a stage list mixing valid and invalid names (no duplicates)
        stages = valid_envs[:2] + actual_invalid
        # Remove duplicates while preserving order
        seen: set[str] = set()
        unique_stages: list[str] = []
        for s in stages:
            if s not in seen:
                seen.add(s)
                unique_stages.append(s)

        # Recompute actual invalid after dedup (some valid_envs entries may overlap)
        final_invalid = [name for name in unique_stages if name not in environments]
        assume(len(final_invalid) >= 1)

        result = validate_pipeline_stages(unique_stages, environments)

        # Must return an error
        assert result is not None, (
            f"Expected error for invalid envs {final_invalid} but got None"
        )
        assert "error" in result

        # Every invalid name must appear in the error message
        for invalid_name in final_invalid:
            assert invalid_name in result["error"], (
                f"Invalid name {invalid_name!r} not found in error: {result['error']!r}"
            )


# --- Property-Based Tests ---

import string

from hypothesis import given, settings
from hypothesis import strategies as st

from appian_deployment_mcp.pipeline.validation import validate_run_params


# Strategies for generating test data
valid_export_types = st.sampled_from(["package", "application"])
invalid_export_types = st.text(min_size=1, max_size=50).filter(
    lambda s: s not in ("package", "application")
)
env_names = st.text(
    alphabet=string.ascii_lowercase + string.digits + "-_",
    min_size=1,
    max_size=20,
)
uuid_strings = st.text(
    alphabet=string.ascii_lowercase + string.digits + "-",
    min_size=5,
    max_size=36,
)


class TestRunParamValidationProperties:
    """Property 18: Run parameter validation.

    Feature: deployment-pipeline, Property 18: Run parameter validation

    Validates: Requirements 2.1, 5.1
    """

    @settings(max_examples=100)
    @given(
        export_type=invalid_export_types,
        uuids=st.lists(uuid_strings, min_size=1, max_size=5),
        stages=st.lists(env_names, min_size=2, max_size=5),
    )
    def test_invalid_export_type_rejected(
        self, export_type: str, uuids: list[str], stages: list[str]
    ) -> None:
        """Any export_type not in {'package', 'application'} produces an error.

        **Validates: Requirements 2.1, 5.1**
        """
        result = validate_run_params(
            uuids=uuids,
            export_type=export_type,
            stages=stages,
            approval_environments=None,
        )
        assert result is not None
        assert "error" in result
        assert "export_type" in result["error"]

    @settings(max_examples=100)
    @given(
        stages=st.lists(env_names, min_size=2, max_size=5),
    )
    def test_empty_uuids_rejected(self, stages: list[str]) -> None:
        """An empty uuids list always produces an error.

        **Validates: Requirements 2.1, 5.1**
        """
        result = validate_run_params(
            uuids=[],
            export_type="package",
            stages=stages,
            approval_environments=None,
        )
        assert result is not None
        assert "error" in result
        assert "uuids" in result["error"]
        assert "at least 1" in result["error"]

    @settings(max_examples=100)
    @given(
        extra_count=st.integers(min_value=1, max_value=50),
        stages=st.lists(env_names, min_size=2, max_size=5),
    )
    def test_oversized_uuids_rejected(
        self, extra_count: int, stages: list[str]
    ) -> None:
        """A uuids list exceeding 100 entries always produces an error.

        **Validates: Requirements 2.1, 5.1**
        """
        uuids = [f"uuid-{i}" for i in range(100 + extra_count)]
        result = validate_run_params(
            uuids=uuids,
            export_type="package",
            stages=stages,
            approval_environments=None,
        )
        assert result is not None
        assert "error" in result
        assert "uuids" in result["error"]
        assert "100" in result["error"]

    @settings(max_examples=100)
    @given(
        uuids=st.lists(uuid_strings, min_size=1, max_size=5),
    )
    def test_adhoc_too_few_stages_rejected(self, uuids: list[str]) -> None:
        """Ad-hoc pipelines with fewer than 2 stages produce an error.

        **Validates: Requirements 2.1, 5.1**
        """
        # 0 or 1 stage with min_stages=2 should fail
        for stage_list in [[], ["dev"]]:
            result = validate_run_params(
                uuids=uuids,
                export_type="package",
                stages=stage_list,
                approval_environments=None,
                min_stages=2,
            )
            assert result is not None
            assert "error" in result
            assert "stages" in result["error"]

    @settings(max_examples=100)
    @given(
        extra_count=st.integers(min_value=1, max_value=30),
        uuids=st.lists(uuid_strings, min_size=1, max_size=5),
    )
    def test_too_many_stages_rejected(
        self, extra_count: int, uuids: list[str]
    ) -> None:
        """A stages list exceeding 20 entries always produces an error.

        **Validates: Requirements 2.1, 5.1**
        """
        stages = [f"env-{i}" for i in range(20 + extra_count)]
        result = validate_run_params(
            uuids=uuids,
            export_type="package",
            stages=stages,
            approval_environments=None,
        )
        assert result is not None
        assert "error" in result
        assert "stages" in result["error"]
        assert "20" in result["error"]

    @settings(max_examples=100)
    @given(
        stages=st.lists(env_names, min_size=2, max_size=10, unique=True),
        extra_envs=st.lists(env_names, min_size=1, max_size=5),
        uuids=st.lists(uuid_strings, min_size=1, max_size=5),
    )
    def test_approval_environments_not_subset_rejected(
        self, stages: list[str], extra_envs: list[str], uuids: list[str]
    ) -> None:
        """approval_environments containing names not in stages produces an error.

        **Validates: Requirements 2.1, 5.1**
        """
        stage_set = set(stages)
        # Filter extra_envs to only those NOT in stages
        invalid_approvals = [e for e in extra_envs if e not in stage_set]
        if not invalid_approvals:
            # Force at least one invalid approval environment
            invalid_approvals = ["__nonexistent_env__"]

        approval_environments = invalid_approvals
        result = validate_run_params(
            uuids=uuids,
            export_type="package",
            stages=stages,
            approval_environments=approval_environments,
        )
        assert result is not None
        assert "error" in result
        assert "approval_environments" in result["error"]
        # Every invalid approval env should be mentioned in the error
        for env in invalid_approvals:
            assert env in result["error"]

    @settings(max_examples=100)
    @given(
        uuids=st.lists(uuid_strings, min_size=1, max_size=10),
        export_type=valid_export_types,
        stages=st.lists(env_names, min_size=2, max_size=10, unique=True),
    )
    def test_valid_params_return_none(
        self, uuids: list[str], export_type: str, stages: list[str]
    ) -> None:
        """Valid parameters (correct export_type, 1-100 uuids, 2-20 stages,
        approval_environments subset of stages) always return None.

        **Validates: Requirements 2.1, 5.1**
        """
        # Use a subset of stages as approval_environments
        approval_environments = stages[:1] if stages else []
        result = validate_run_params(
            uuids=uuids,
            export_type=export_type,
            stages=stages,
            approval_environments=approval_environments,
        )
        assert result is None
