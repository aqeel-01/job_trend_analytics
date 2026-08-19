"""Model evaluation result types."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class RankingStabilityMetric:
    """Measures how stable the trend model ranking is compared to baseline."""

    kendall_tau: float | None
    spearman_rho: float | None
    description: str


@dataclass(frozen=True)
class TopKOverlapMetric:
    """Top-k skill overlap between trend model and baseline."""

    k: int
    trend_model_top_k: tuple[str, ...]
    baseline_top_k: tuple[str, ...]
    overlap: tuple[str, ...]
    overlap_ratio: float
    description: str


@dataclass(frozen=True)
class ChangeDetectionMetric:
    """Ability to detect genuine changes vs noise."""

    skills_with_z_score: int
    rising_detected: int
    falling_detected: int
    stable_detected: int
    insufficient_data: int
    description: str


@dataclass(frozen=True)
class HistoricalValidationMetric:
    """Retrospective validation using held-out periods."""

    periods_evaluated: int
    hit_rate_at_k: float | None
    k: int
    description: str


@dataclass(frozen=True)
class DatasetLimitation:
    """Explicit documentation of dataset limitations per SRS."""

    code: str
    message: str
    severity: str


@dataclass(frozen=True)
class EvaluationReport:
    """Structured V1 model evaluation result."""

    generated_at: datetime
    trend_model_version: str
    baseline_name: str
    period_count: int
    skill_count: int
    ranking_stability: RankingStabilityMetric
    top_k_overlap: TopKOverlapMetric
    change_detection: ChangeDetectionMetric
    historical_validation: HistoricalValidationMetric
    limitations: tuple[DatasetLimitation, ...]

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary."""
        import dataclasses

        def _convert(obj):
            if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
                return {k: _convert(v) for k, v in dataclasses.asdict(obj).items()}
            if isinstance(obj, tuple):
                return [_convert(item) for item in obj]
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj

        return _convert(self)
