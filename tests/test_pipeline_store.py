"""Unit tests for PipelineStore."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pytest

from appian_deployment_mcp.pipeline.models import (
    PipelineStatus,
    RunConfig,
    StageStatus,
)
from appian_deployment_mcp.pipeline.store import PipelineStore


class TestCreateDefinition:
    """Tests for PipelineStore.create_definition."""

    def test_creates_definition_with_name_and_stages(self):
        store = PipelineStore()
        defn = store.create_definition("my-pipeline", ["dev", "test", "prod"])
        assert defn.name == "my-pipeline"
        assert defn.stages == ["dev", "test", "prod"]
        assert isinstance(defn.created_at, datetime)

    def test_overwrites_existing_definition(self):
        store = PipelineStore()
        store.create_definition("my-pipeline", ["dev", "test"])
        defn = store.create_definition("my-pipeline", ["dev", "staging", "prod"])
        assert defn.stages == ["dev", "staging", "prod"]
        # Only one definition should exist
        assert len(store.list_definitions()) == 1


class TestGetDefinition:
    """Tests for PipelineStore.get_definition."""

    def test_returns_definition_when_exists(self):
        store = PipelineStore()
        store.create_definition("my-pipeline", ["dev", "prod"])
        result = store.get_definition("my-pipeline")
        assert result is not None
        assert result.name == "my-pipeline"
        assert result.stages == ["dev", "prod"]

    def test_returns_none_when_not_found(self):
        store = PipelineStore()
        assert store.get_definition("nonexistent") is None


class TestListDefinitions:
    """Tests for PipelineStore.list_definitions."""

    def test_returns_empty_list_when_no_definitions(self):
        store = PipelineStore()
        assert store.list_definitions() == []

    def test_returns_all_definitions(self):
        store = PipelineStore()
        store.create_definition("pipeline-a", ["dev", "prod"])
        store.create_definition("pipeline-b", ["dev", "test", "prod"])
        result = store.list_definitions()
        assert len(result) == 2
        names = {d.name for d in result}
        assert names == {"pipeline-a", "pipeline-b"}


class TestCreateRun:
    """Tests for PipelineStore.create_run."""

    def test_creates_run_with_uuid_and_pending_status(self):
        store = PipelineStore()
        config = RunConfig(
            uuids=["uuid-1"],
            export_type="package",
            export_name="test-export",
        )
        run = store.create_run("my-pipeline", config, ["dev", "test", "prod"])
        assert run.run_id  # non-empty UUID string
        assert run.pipeline_name == "my-pipeline"
        assert run.status == PipelineStatus.PENDING
        assert len(run.stages) == 3
        assert run.config is config

    def test_stages_are_pending_with_correct_numbers(self):
        store = PipelineStore()
        config = RunConfig(
            uuids=["uuid-1"],
            export_type="package",
            export_name="test-export",
        )
        run = store.create_run("my-pipeline", config, ["dev", "test", "prod"])
        for i, stage in enumerate(run.stages):
            assert stage.status == StageStatus.PENDING
            assert stage.stage_number == i + 1
            assert stage.environment == ["dev", "test", "prod"][i]

    def test_creates_asyncio_events(self):
        store = PipelineStore()
        config = RunConfig(
            uuids=["uuid-1"],
            export_type="package",
            export_name="test-export",
        )
        run = store.create_run("my-pipeline", config, ["dev", "prod"])
        assert isinstance(run._cancel_event, asyncio.Event)
        assert isinstance(run._approval_event, asyncio.Event)
        assert not run._cancel_event.is_set()
        assert not run._approval_event.is_set()

    def test_run_ids_are_unique(self):
        store = PipelineStore()
        config = RunConfig(
            uuids=["uuid-1"],
            export_type="package",
            export_name="test-export",
        )
        ids = set()
        for _ in range(50):
            run = store.create_run("pipeline", config, ["dev", "prod"])
            ids.add(run.run_id)
        assert len(ids) == 50


class TestGetRun:
    """Tests for PipelineStore.get_run."""

    def test_returns_run_when_exists(self):
        store = PipelineStore()
        config = RunConfig(
            uuids=["uuid-1"],
            export_type="package",
            export_name="test-export",
        )
        created = store.create_run("my-pipeline", config, ["dev", "prod"])
        result = store.get_run(created.run_id)
        assert result is created

    def test_returns_none_when_not_found(self):
        store = PipelineStore()
        assert store.get_run("nonexistent-id") is None


class TestListRuns:
    """Tests for PipelineStore.list_runs."""

    def test_returns_empty_list_when_no_runs(self):
        store = PipelineStore()
        assert store.list_runs() == []

    def test_returns_runs_sorted_by_created_at_descending(self):
        store = PipelineStore()
        config = RunConfig(
            uuids=["uuid-1"],
            export_type="package",
            export_name="test-export",
        )
        # Create runs with distinct timestamps
        run1 = store.create_run("pipeline", config, ["dev", "prod"])
        run1.created_at = datetime(2024, 1, 1)
        run2 = store.create_run("pipeline", config, ["dev", "prod"])
        run2.created_at = datetime(2024, 1, 3)
        run3 = store.create_run("pipeline", config, ["dev", "prod"])
        run3.created_at = datetime(2024, 1, 2)

        result = store.list_runs()
        assert result[0].run_id == run2.run_id  # most recent
        assert result[1].run_id == run3.run_id
        assert result[2].run_id == run1.run_id  # oldest

    def test_caps_at_limit(self):
        store = PipelineStore()
        config = RunConfig(
            uuids=["uuid-1"],
            export_type="package",
            export_name="test-export",
        )
        for _ in range(150):
            store.create_run("pipeline", config, ["dev", "prod"])

        result = store.list_runs(limit=100)
        assert len(result) == 100

    def test_custom_limit(self):
        store = PipelineStore()
        config = RunConfig(
            uuids=["uuid-1"],
            export_type="package",
            export_name="test-export",
        )
        for _ in range(10):
            store.create_run("pipeline", config, ["dev", "prod"])

        result = store.list_runs(limit=5)
        assert len(result) == 5
