"""Trend model result types."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class TrendDirection(StrEnum):
    """Direction of skill demand movement."""

    UP = "up"
    DOWN = "down"
    FLAT = "flat"
    UNKNOWN = "unknown"


class TrendLabel(StrEnum):
    """Human-readable trend classification."""

    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    INSUFFICIENT_DATA = "insufficient_data"


DEFAULT_MODEL_VERSION = "v1.0"
DEFAULT_MIN_HISTORY_PERIODS = 2
DEFAULT_Z_RISING_THRESHOLD = 0.5
DEFAULT_Z_FALLING_THRESHOLD = -0.5


@dataclass(frozen=True)
class SkillTrendScore:
    """Trend statistics for a single skill."""

    skill: str
    current_mentions: int
    previous_mentions: int
    change: int
    change_percent: float | None
    historical_mean: float | None
    historical_std: float | None
    z_score: float | None
    trend: TrendLabel
    direction: TrendDirection


@dataclass(frozen=True)
class TrendModelResult:
    """Ranked output from the V1 statistical trend model."""

    model_version: str
    generated_at: datetime
    period_count: int
    skills: tuple[SkillTrendScore, ...]
