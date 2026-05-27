"""Data models for the deployment pipeline feature."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class PipelineStatus(str, Enum):
    """Overall status of a pipeline run."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StageStatus(str, Enum):
    """Status of a single pipeline stage."""

    PENDING = "PENDING"
    EXPORTING = "EXPORTING"
    INSPECTING = "INSPECTING"
    DEPLOYING = "DEPLOYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class StageOperation(str, Enum):
    """Type of operation performed in a pipeline stage."""

    EXPORT = "export"
    INSPECT = "inspect"
    IMPORT = "import"


@dataclass
class StageResult:
    """Outcome data for a completed or failed pipeline stage."""

    environment: str
    operation: StageOperation
    deployment_uuid: str | None = None
    status: str = ""
    package_path: str | None = None
    deployment_log_url: str | None = None
    errors: list[dict] | None = None
    warnings: list[dict] | None = None
    object_counts: dict | None = None
    error_type: str | None = None
    error_domain: str | None = None


@dataclass
class PipelineStage:
    """A single stage within a pipeline run."""

    environment: str
    stage_number: int
    status: StageStatus = StageStatus.PENDING
    operation: StageOperation | None = None
    result: StageResult | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True)
class RunConfig:
    """Parameters for a pipeline execution."""

    uuids: list[str]
    export_type: str
    export_name: str
    deploy_name_template: str | None = None
    customization_file_path: str | None = None
    inspect_before_deploy: bool = True
    approval_environments: list[str] = field(default_factory=list)

    def __hash__(self) -> int:
        return hash((
            tuple(self.uuids),
            self.export_type,
            self.export_name,
            self.deploy_name_template,
            self.customization_file_path,
            self.inspect_before_deploy,
            tuple(self.approval_environments),
        ))


@dataclass(frozen=True)
class PipelineDefinition:
    """A named, ordered list of environments defining a promotion path."""

    name: str
    stages: list[str]
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __hash__(self) -> int:
        return hash((self.name, tuple(self.stages), self.created_at))


@dataclass
class PipelineRun:
    """A single execution of a pipeline."""

    run_id: str
    pipeline_name: str
    status: PipelineStatus
    stages: list[PipelineStage]
    config: RunConfig
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    cancellation_reason: str | None = None
    rejection_reason: str | None = None
    approval_comment: str | None = None
    _cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    _approval_event: asyncio.Event = field(default_factory=asyncio.Event)
    _approval_granted: bool = False
