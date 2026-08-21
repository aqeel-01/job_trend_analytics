"""Result types for V1 retraining and model-version comparison."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RetrainResult:
    """Outcome of a single train/retrain run."""

    run_id: int
    model_version: str
    previous_version: str | None
    trained_at: datetime
    training_dataset_size: int
    period_count: int
    model_parameters: dict[str, Any]
    evaluation_metrics: dict[str, Any]
    status: str
    used_new_data: bool
    skipped: bool = False
    skip_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["trained_at"] = self.trained_at.isoformat()
        return payload


@dataclass(frozen=True)
class SkillRankingDelta:
    """How a skill's rank changed between two model versions."""

    skill: str
    previous_rank: int | None
    current_rank: int | None
    rank_change: int | None


@dataclass(frozen=True)
class ModelVersionComparison:
    """Structured comparison between two persisted model runs."""

    previous_version: str
    current_version: str
    previous_run_id: int
    current_run_id: int
    previous_trained_at: datetime | None
    current_trained_at: datetime | None
    previous_dataset_size: int | None
    current_dataset_size: int | None
    dataset_size_delta: int | None
    previous_metrics: dict[str, Any]
    current_metrics: dict[str, Any]
    metric_deltas: dict[str, Any]
    top_k: int
    previous_top_skills: list[str]
    current_top_skills: list[str]
    top_k_overlap: list[str]
    top_k_overlap_ratio: float
    ranking_deltas: list[SkillRankingDelta] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "previous_version": self.previous_version,
            "current_version": self.current_version,
            "previous_run_id": self.previous_run_id,
            "current_run_id": self.current_run_id,
            "previous_trained_at": (
                self.previous_trained_at.isoformat() if self.previous_trained_at else None
            ),
            "current_trained_at": (
                self.current_trained_at.isoformat() if self.current_trained_at else None
            ),
            "previous_dataset_size": self.previous_dataset_size,
            "current_dataset_size": self.current_dataset_size,
            "dataset_size_delta": self.dataset_size_delta,
            "previous_metrics": self.previous_metrics,
            "current_metrics": self.current_metrics,
            "metric_deltas": self.metric_deltas,
            "top_k": self.top_k,
            "previous_top_skills": self.previous_top_skills,
            "current_top_skills": self.current_top_skills,
            "top_k_overlap": self.top_k_overlap,
            "top_k_overlap_ratio": self.top_k_overlap_ratio,
            "ranking_deltas": [asdict(d) for d in self.ranking_deltas],
            "summary": self.summary,
        }
