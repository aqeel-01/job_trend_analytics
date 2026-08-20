"""V1 local monitoring metrics — names and event types."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MetricName(str, Enum):
    """Canonical V1 metric names from the SRS monitoring checklist."""

    API_FAILURES = "api_failures"
    INGESTION_LATENCY = "ingestion_latency"
    JOBS_COLLECTED = "jobs_collected"
    DUPLICATE_PERCENTAGE = "duplicate_percentage"
    PREPROCESSING_FAILURES = "preprocessing_failures"
    MODEL_EXECUTION_TIME = "model_execution_time"
    AGENT_EXECUTION_FAILURES = "agent_execution_failures"
    FASTAPI_HEALTH = "fastapi_health"
    REPORT_GENERATION_SUCCESS = "report_generation_success"


@dataclass(frozen=True)
class MetricEvent:
    """A single recorded monitoring observation."""

    name: str
    recorded_at: str
    value: float | int | None = None
    unit: str | None = None
    success: bool | None = None
    labels: dict[str, Any] = field(default_factory=dict)
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def create(
        cls,
        name: str | MetricName,
        *,
        value: float | int | None = None,
        unit: str | None = None,
        success: bool | None = None,
        labels: dict[str, Any] | None = None,
        detail: str | None = None,
        recorded_at: datetime | None = None,
    ) -> MetricEvent:
        ts = recorded_at or datetime.now(timezone.utc)
        return cls(
            name=name.value if isinstance(name, MetricName) else name,
            recorded_at=ts.isoformat(),
            value=value,
            unit=unit,
            success=success,
            labels=labels or {},
            detail=detail,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> MetricEvent:
        return cls(
            name=str(payload["name"]),
            recorded_at=str(payload["recorded_at"]),
            value=payload.get("value"),
            unit=payload.get("unit"),
            success=payload.get("success"),
            labels=dict(payload.get("labels") or {}),
            detail=payload.get("detail"),
        )
