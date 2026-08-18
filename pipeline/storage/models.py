"""Persistence-layer record types."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StoredJob:
    """Job record as stored in SQLite."""

    id: int
    source_job_id: str
    title: str
    company: str
    location: str | None
    description: str
    url: str
    published_at: datetime | None
    remote: bool | None
    source: str
    ingested_at: datetime
    created_at: datetime


@dataclass(frozen=True)
class JobInsertResult:
    """Outcome of attempting to insert a job."""

    inserted: bool
    job_id: int | None


@dataclass(frozen=True)
class StoredSkill:
    """Skill taxonomy record."""

    id: int
    skill_name: str
    category: str | None
    canonical_name: str
    created_at: datetime


@dataclass(frozen=True)
class StoredJobSkill:
    """Association between a job and an extracted skill."""

    id: int
    job_id: int
    skill_id: int
    confidence: float | None
    extraction_method: str | None
    created_at: datetime


@dataclass(frozen=True)
class StoredPipelineRun:
    """Pipeline execution metadata."""

    id: int
    started_at: datetime
    completed_at: datetime | None
    status: str
    records_fetched: int
    records_inserted: int
    records_failed: int
    error_message: str | None
    created_at: datetime


@dataclass(frozen=True)
class StoredModelRun:
    """Model training run metadata."""

    id: int
    model_version: str
    trained_at: datetime
    training_dataset_size: int | None
    model_parameters: str | None
    evaluation_metrics: str | None
    status: str
    created_at: datetime


@dataclass(frozen=True)
class StoredAgentRun:
    """Agent workflow execution metadata."""

    id: int
    started_at: datetime
    completed_at: datetime | None
    status: str
    workflow_name: str | None
    tool_calls_succeeded: int
    tool_calls_failed: int
    output_path: str | None
    error_message: str | None
    created_at: datetime
