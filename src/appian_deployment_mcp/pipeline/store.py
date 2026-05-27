"""In-memory storage for pipeline definitions and runs."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

from .models import (
    PipelineDefinition,
    PipelineRun,
    PipelineStage,
    PipelineStatus,
    RunConfig,
    StageStatus,
)


class PipelineStore:
    """In-memory storage for pipeline definitions and runs."""

    def __init__(self) -> None:
        self._definitions: dict[str, PipelineDefinition] = {}
        self._runs: dict[str, PipelineRun] = {}

    def create_definition(self, name: str, stages: list[str]) -> PipelineDefinition:
        """Store a pipeline definition, overwriting if name already exists."""
        definition = PipelineDefinition(name=name, stages=stages)
        self._definitions[name] = definition
        return definition

    def get_definition(self, name: str) -> PipelineDefinition | None:
        """Return a pipeline definition by name, or None if not found."""
        return self._definitions.get(name)

    def list_definitions(self) -> list[PipelineDefinition]:
        """Return all pipeline definitions as a list."""
        return list(self._definitions.values())

    def create_run(
        self,
        definition_name: str,
        config: RunConfig,
        stages: list[str],
    ) -> PipelineRun:
        """Create a new pipeline run with PENDING stages and asyncio.Event instances.

        Args:
            definition_name: Name of the pipeline definition (or "__adhoc__").
            config: Execution parameters for the run.
            stages: Ordered list of environment names for the run.

        Returns:
            The newly created PipelineRun with a unique UUID4 run_id.
        """
        run_id = str(uuid.uuid4())
        pipeline_stages = [
            PipelineStage(
                environment=env,
                stage_number=i + 1,
                status=StageStatus.PENDING,
            )
            for i, env in enumerate(stages)
        ]
        run = PipelineRun(
            run_id=run_id,
            pipeline_name=definition_name,
            status=PipelineStatus.PENDING,
            stages=pipeline_stages,
            config=config,
            created_at=datetime.utcnow(),
        )
        self._runs[run_id] = run
        return run

    def get_run(self, run_id: str) -> PipelineRun | None:
        """Return a pipeline run by ID, or None if not found."""
        return self._runs.get(run_id)

    def list_runs(self, limit: int = 100) -> list[PipelineRun]:
        """Return the most recent pipeline runs, sorted by created_at descending.

        Args:
            limit: Maximum number of runs to return (default 100).

        Returns:
            List of PipelineRun instances, most recent first, capped at limit.
        """
        sorted_runs = sorted(
            self._runs.values(),
            key=lambda r: r.created_at,
            reverse=True,
        )
        return sorted_runs[:limit]
