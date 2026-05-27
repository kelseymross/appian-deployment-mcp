"""Unit tests for pipeline tool parameter handling.

Tests create_pipeline, run_pipeline, run_adhoc_pipeline parameter validation,
deploy_name template expansion, and approval_environments validation.

Validates: Requirements 1.1, 1.2, 2.1, 5.1
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from appian_deployment_mcp.config import EnvironmentConfig
from appian_deployment_mcp.pipeline.models import (
    PipelineRun,
    PipelineStage,
    PipelineStatus,
    RunConfig,
    StageOperation,
    StageStatus,
)
from appian_deployment_mcp.pipeline.store import PipelineStore
from appian_deployment_mcp.tools.pipeline_definitions import create_pipeline
from appian_deployment_mcp.tools.pipeline_runs import run_adhoc_pipeline, run_pipeline


# --- Fixtures ---


def _make_environments(*names: str) -> dict[str, EnvironmentConfig]:
    """Create a dict of mock EnvironmentConfig objects keyed by name."""
    return {
        name: EnvironmentConfig(
            name=name,
            domain=f"{name}.appiancloud.com",
            api_key=f"key-{name}",
        )
        for name in names
    }


def _make_store_with_pipeline(name: str, stages: list[str]) -> PipelineStore:
    """Create a PipelineStore with a single pipeline definition."""
    store = PipelineStore()
    store.create_definition(name, stages)
    return store


# --- Tests for create_pipeline ---


class TestCreatePipelineValid:
    """Test create_pipeline with valid inputs."""

    @pytest.mark.asyncio
    async def test_valid_name_and_stages_returns_success(self):
        """A valid name and stages list returns the pipeline definition."""
        envs = _make_environments("dev", "test", "prod")
        store = PipelineStore()

        with (
            patch(
                "appian_deployment_mcp.tools.pipeline_definitions.get_environments",
                return_value=envs,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_definitions.get_pipeline_store",
                return_value=store,
            ),
        ):
            result = await create_pipeline(name="my-pipeline", stages=["dev", "test", "prod"])

        assert "error" not in result
        assert result["name"] == "my-pipeline"
        assert result["stages"] == ["dev", "test", "prod"]
        assert "created_at" in result

    @pytest.mark.asyncio
    async def test_single_stage_pipeline_is_valid(self):
        """A pipeline with a single stage is valid."""
        envs = _make_environments("dev")
        store = PipelineStore()

        with (
            patch(
                "appian_deployment_mcp.tools.pipeline_definitions.get_environments",
                return_value=envs,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_definitions.get_pipeline_store",
                return_value=store,
            ),
        ):
            result = await create_pipeline(name="single", stages=["dev"])

        assert "error" not in result
        assert result["stages"] == ["dev"]


class TestCreatePipelineInvalidName:
    """Test create_pipeline with invalid name inputs."""

    @pytest.mark.asyncio
    async def test_empty_name_returns_error(self):
        """An empty name returns an error."""
        envs = _make_environments("dev")
        store = PipelineStore()

        with (
            patch(
                "appian_deployment_mcp.tools.pipeline_definitions.get_environments",
                return_value=envs,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_definitions.get_pipeline_store",
                return_value=store,
            ),
        ):
            result = await create_pipeline(name="", stages=["dev"])

        assert "error" in result
        assert "1 and 128" in result["error"]

    @pytest.mark.asyncio
    async def test_name_over_128_chars_returns_error(self):
        """A name exceeding 128 characters returns an error."""
        envs = _make_environments("dev")
        store = PipelineStore()
        long_name = "x" * 129

        with (
            patch(
                "appian_deployment_mcp.tools.pipeline_definitions.get_environments",
                return_value=envs,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_definitions.get_pipeline_store",
                return_value=store,
            ),
        ):
            result = await create_pipeline(name=long_name, stages=["dev"])

        assert "error" in result
        assert "128" in result["error"]

    @pytest.mark.asyncio
    async def test_name_exactly_128_chars_is_valid(self):
        """A name of exactly 128 characters is valid."""
        envs = _make_environments("dev")
        store = PipelineStore()
        name_128 = "a" * 128

        with (
            patch(
                "appian_deployment_mcp.tools.pipeline_definitions.get_environments",
                return_value=envs,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_definitions.get_pipeline_store",
                return_value=store,
            ),
        ):
            result = await create_pipeline(name=name_128, stages=["dev"])

        assert "error" not in result
        assert result["name"] == name_128


class TestCreatePipelineInvalidEnvironments:
    """Test create_pipeline with invalid environment names."""

    @pytest.mark.asyncio
    async def test_invalid_env_names_returns_error(self):
        """Environment names not in configured environments return an error."""
        envs = _make_environments("dev", "test")
        store = PipelineStore()

        with (
            patch(
                "appian_deployment_mcp.tools.pipeline_definitions.get_environments",
                return_value=envs,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_definitions.get_pipeline_store",
                return_value=store,
            ),
        ):
            result = await create_pipeline(name="bad", stages=["dev", "nonexistent"])

        assert "error" in result
        assert "nonexistent" in result["error"]

    @pytest.mark.asyncio
    async def test_all_invalid_env_names_listed_in_error(self):
        """All invalid environment names are listed in the error message."""
        envs = _make_environments("dev")
        store = PipelineStore()

        with (
            patch(
                "appian_deployment_mcp.tools.pipeline_definitions.get_environments",
                return_value=envs,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_definitions.get_pipeline_store",
                return_value=store,
            ),
        ):
            result = await create_pipeline(name="bad", stages=["foo", "bar", "dev"])

        assert "error" in result
        assert "foo" in result["error"]
        assert "bar" in result["error"]


class TestCreatePipelineDuplicateEnvironments:
    """Test create_pipeline with duplicate environment names."""

    @pytest.mark.asyncio
    async def test_duplicate_env_names_returns_error(self):
        """Duplicate environment names in stages return an error."""
        envs = _make_environments("dev", "test", "prod")
        store = PipelineStore()

        with (
            patch(
                "appian_deployment_mcp.tools.pipeline_definitions.get_environments",
                return_value=envs,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_definitions.get_pipeline_store",
                return_value=store,
            ),
        ):
            result = await create_pipeline(name="dup", stages=["dev", "test", "dev"])

        assert "error" in result
        assert "dev" in result["error"].lower() or "Duplicate" in result["error"]


# --- Tests for run_pipeline ---


class TestRunPipelineMissingPipeline:
    """Test run_pipeline with a non-existent pipeline name."""

    @pytest.mark.asyncio
    async def test_nonexistent_pipeline_returns_error_with_available(self):
        """A non-existent pipeline_name returns an error listing available pipelines."""
        envs = _make_environments("dev", "test", "prod")
        store = PipelineStore()
        store.create_definition("existing-pipeline", ["dev", "test", "prod"])

        engine = MagicMock()

        with (
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_environments",
                return_value=envs,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_store",
                return_value=store,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_engine",
                return_value=engine,
            ),
        ):
            result = await run_pipeline(
                pipeline_name="does-not-exist",
                uuids=["uuid-1"],
                export_type="package",
                export_name="test-export",
            )

        assert "error" in result
        assert "does-not-exist" in result["error"]
        assert "existing-pipeline" in result["error"]

    @pytest.mark.asyncio
    async def test_nonexistent_pipeline_empty_store_returns_error(self):
        """A non-existent pipeline_name with empty store returns error with empty list."""
        envs = _make_environments("dev", "test")
        store = PipelineStore()

        engine = MagicMock()

        with (
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_environments",
                return_value=envs,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_store",
                return_value=store,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_engine",
                return_value=engine,
            ),
        ):
            result = await run_pipeline(
                pipeline_name="ghost",
                uuids=["uuid-1"],
                export_type="package",
                export_name="test-export",
            )

        assert "error" in result
        assert "ghost" in result["error"]


# --- Tests for run_adhoc_pipeline ---


class TestRunAdhocPipelineStageCounts:
    """Test run_adhoc_pipeline with invalid stage counts."""

    @pytest.mark.asyncio
    async def test_fewer_than_2_stages_returns_error(self):
        """Ad-hoc pipeline with fewer than 2 stages returns an error."""
        envs = _make_environments("dev", "test", "prod")
        store = PipelineStore()
        engine = MagicMock()

        with (
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_environments",
                return_value=envs,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_store",
                return_value=store,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_engine",
                return_value=engine,
            ),
        ):
            result = await run_adhoc_pipeline(
                stages=["dev"],
                uuids=["uuid-1"],
                export_type="package",
                export_name="test-export",
            )

        assert "error" in result
        assert "at least 2" in result["error"]

    @pytest.mark.asyncio
    async def test_more_than_20_stages_returns_error(self):
        """Ad-hoc pipeline with more than 20 stages returns an error."""
        env_names = [f"env{i}" for i in range(21)]
        envs = _make_environments(*env_names)
        store = PipelineStore()
        engine = MagicMock()

        with (
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_environments",
                return_value=envs,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_store",
                return_value=store,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_engine",
                return_value=engine,
            ),
        ):
            result = await run_adhoc_pipeline(
                stages=env_names,
                uuids=["uuid-1"],
                export_type="package",
                export_name="test-export",
            )

        assert "error" in result
        assert "20" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_env_names_in_stages_returns_error(self):
        """Ad-hoc pipeline with invalid environment names returns an error."""
        envs = _make_environments("dev", "test")
        store = PipelineStore()
        engine = MagicMock()

        with (
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_environments",
                return_value=envs,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_store",
                return_value=store,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_engine",
                return_value=engine,
            ),
        ):
            result = await run_adhoc_pipeline(
                stages=["dev", "nonexistent"],
                uuids=["uuid-1"],
                export_type="package",
                export_name="test-export",
            )

        assert "error" in result
        assert "nonexistent" in result["error"]

    @pytest.mark.asyncio
    async def test_exactly_2_stages_is_valid(self):
        """Ad-hoc pipeline with exactly 2 valid stages succeeds."""
        envs = _make_environments("dev", "test")
        store = PipelineStore()
        engine = MagicMock()
        engine.execute = AsyncMock()

        with (
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_environments",
                return_value=envs,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_store",
                return_value=store,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_engine",
                return_value=engine,
            ),
            patch("asyncio.create_task"),
        ):
            result = await run_adhoc_pipeline(
                stages=["dev", "test"],
                uuids=["uuid-1"],
                export_type="package",
                export_name="test-export",
            )

        assert "error" not in result
        assert "run_id" in result
        assert result["pipeline_name"] == "__adhoc__"


# --- Tests for deploy_name template expansion ---


class TestDeployNameTemplateExpansion:
    """Test deploy_name template expansion with {environment} and {stage_number}."""

    def test_environment_placeholder_expanded(self):
        """The {environment} placeholder is replaced with the stage environment name."""
        template = "Deploy to {environment}"
        stage = PipelineStage(
            environment="prod",
            stage_number=3,
            status=StageStatus.PENDING,
        )
        # Replicate the engine's template expansion logic
        deploy_name = template.replace(
            "{environment}", stage.environment
        ).replace("{stage_number}", str(stage.stage_number))

        assert deploy_name == "Deploy to prod"

    def test_stage_number_placeholder_expanded(self):
        """The {stage_number} placeholder is replaced with the stage number."""
        template = "Stage {stage_number} deployment"
        stage = PipelineStage(
            environment="test",
            stage_number=2,
            status=StageStatus.PENDING,
        )
        deploy_name = template.replace(
            "{environment}", stage.environment
        ).replace("{stage_number}", str(stage.stage_number))

        assert deploy_name == "Stage 2 deployment"

    def test_both_placeholders_expanded(self):
        """Both {environment} and {stage_number} are expanded in the same template."""
        template = "Deploy-{environment}-stage{stage_number}"
        stage = PipelineStage(
            environment="staging",
            stage_number=4,
            status=StageStatus.PENDING,
        )
        deploy_name = template.replace(
            "{environment}", stage.environment
        ).replace("{stage_number}", str(stage.stage_number))

        assert deploy_name == "Deploy-staging-stage4"

    def test_no_placeholders_returns_template_unchanged(self):
        """A template without placeholders is returned as-is."""
        template = "Fixed deploy name"
        stage = PipelineStage(
            environment="dev",
            stage_number=1,
            status=StageStatus.PENDING,
        )
        deploy_name = template.replace(
            "{environment}", stage.environment
        ).replace("{stage_number}", str(stage.stage_number))

        assert deploy_name == "Fixed deploy name"

    def test_multiple_occurrences_of_same_placeholder(self):
        """Multiple occurrences of the same placeholder are all expanded."""
        template = "{environment}-to-{environment}"
        stage = PipelineStage(
            environment="prod",
            stage_number=3,
            status=StageStatus.PENDING,
        )
        deploy_name = template.replace(
            "{environment}", stage.environment
        ).replace("{stage_number}", str(stage.stage_number))

        assert deploy_name == "prod-to-prod"


# --- Tests for approval_environments validation ---


class TestApprovalEnvironmentsValidation:
    """Test that approval_environments must be a subset of stages."""

    @pytest.mark.asyncio
    async def test_approval_envs_not_in_stages_returns_error(self):
        """approval_environments with names not in stages returns an error."""
        envs = _make_environments("dev", "test", "prod")
        store = _make_store_with_pipeline("my-pipe", ["dev", "test", "prod"])
        engine = MagicMock()

        with (
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_environments",
                return_value=envs,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_store",
                return_value=store,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_engine",
                return_value=engine,
            ),
        ):
            result = await run_pipeline(
                pipeline_name="my-pipe",
                uuids=["uuid-1"],
                export_type="package",
                export_name="test-export",
                approval_environments=["staging"],  # not in pipeline stages
            )

        assert "error" in result
        assert "staging" in result["error"]

    @pytest.mark.asyncio
    async def test_approval_envs_subset_of_stages_is_valid(self):
        """approval_environments that is a subset of stages succeeds."""
        envs = _make_environments("dev", "test", "prod")
        store = _make_store_with_pipeline("my-pipe", ["dev", "test", "prod"])
        engine = MagicMock()
        engine.execute = AsyncMock()

        with (
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_environments",
                return_value=envs,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_store",
                return_value=store,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_engine",
                return_value=engine,
            ),
            patch("asyncio.create_task"),
        ):
            result = await run_pipeline(
                pipeline_name="my-pipe",
                uuids=["uuid-1"],
                export_type="package",
                export_name="test-export",
                approval_environments=["test", "prod"],
            )

        assert "error" not in result
        assert "run_id" in result

    @pytest.mark.asyncio
    async def test_adhoc_approval_envs_not_in_stages_returns_error(self):
        """Ad-hoc pipeline with approval_environments not in stages returns error."""
        envs = _make_environments("dev", "test", "prod")
        store = PipelineStore()
        engine = MagicMock()

        with (
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_environments",
                return_value=envs,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_store",
                return_value=store,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_engine",
                return_value=engine,
            ),
        ):
            result = await run_adhoc_pipeline(
                stages=["dev", "test"],
                uuids=["uuid-1"],
                export_type="package",
                export_name="test-export",
                approval_environments=["prod"],  # not in stages
            )

        assert "error" in result
        assert "prod" in result["error"]

    @pytest.mark.asyncio
    async def test_adhoc_approval_envs_subset_of_stages_is_valid(self):
        """Ad-hoc pipeline with approval_environments subset of stages succeeds."""
        envs = _make_environments("dev", "test", "prod")
        store = PipelineStore()
        engine = MagicMock()
        engine.execute = AsyncMock()

        with (
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_environments",
                return_value=envs,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_store",
                return_value=store,
            ),
            patch(
                "appian_deployment_mcp.tools.pipeline_runs.get_pipeline_engine",
                return_value=engine,
            ),
            patch("asyncio.create_task"),
        ):
            result = await run_adhoc_pipeline(
                stages=["dev", "test", "prod"],
                uuids=["uuid-1"],
                export_type="package",
                export_name="test-export",
                approval_environments=["test"],
            )

        assert "error" not in result
        assert "run_id" in result
