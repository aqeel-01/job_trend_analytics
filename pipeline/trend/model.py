"""V1 statistical z-score trend model for skill demand."""

import statistics
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

from pipeline.trend.models import (
    DEFAULT_MIN_HISTORY_PERIODS,
    DEFAULT_MODEL_VERSION,
    DEFAULT_Z_FALLING_THRESHOLD,
    DEFAULT_Z_RISING_THRESHOLD,
    SkillTrendScore,
    TrendDirection,
    TrendLabel,
    TrendModelResult,
)


def _change_percent(current: int, previous: int) -> float | None:
    if previous == 0:
        if current == 0:
            return 0.0
        return None
    return ((current - previous) / previous) * 100.0


def _historical_stats(values: list[int]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    mean = statistics.mean(values)
    if len(values) < 2:
        return mean, None
    std = statistics.pstdev(values)
    return mean, std


def _compute_z_score(
    current: int,
    historical_mean: float | None,
    historical_std: float | None,
    history_count: int,
    min_history_periods: int,
) -> float | None:
    if historical_mean is None or history_count < min_history_periods:
        return None
    if historical_std is None:
        return None
    if historical_std == 0:
        if current == historical_mean:
            return 0.0
        return 1.0 if current > historical_mean else -1.0
    return (current - historical_mean) / historical_std


def _classify_trend(
    z_score: float | None,
    change: int,
    history_count: int,
    min_history_periods: int,
    rising_threshold: float,
    falling_threshold: float,
) -> tuple[TrendLabel, TrendDirection]:
    if history_count < min_history_periods:
        return TrendLabel.INSUFFICIENT_DATA, TrendDirection.UNKNOWN

    if z_score is not None:
        if z_score > rising_threshold:
            return TrendLabel.RISING, TrendDirection.UP
        if z_score < falling_threshold:
            return TrendLabel.FALLING, TrendDirection.DOWN
        return TrendLabel.STABLE, TrendDirection.FLAT

    if change > 0:
        return TrendLabel.RISING, TrendDirection.UP
    if change < 0:
        return TrendLabel.FALLING, TrendDirection.DOWN
    return TrendLabel.STABLE, TrendDirection.FLAT


class TrendModel:
    """Deterministic z-score trend model for weekly skill mention frequencies."""

    def __init__(
        self,
        model_version: str = DEFAULT_MODEL_VERSION,
        min_history_periods: int = DEFAULT_MIN_HISTORY_PERIODS,
        z_rising_threshold: float = DEFAULT_Z_RISING_THRESHOLD,
        z_falling_threshold: float = DEFAULT_Z_FALLING_THRESHOLD,
    ) -> None:
        self.model_version = model_version
        self.min_history_periods = min_history_periods
        self.z_rising_threshold = z_rising_threshold
        self.z_falling_threshold = z_falling_threshold

    def compute(
        self,
        weekly_counts: Sequence[Mapping[str, int]],
    ) -> TrendModelResult:
        """
        Compute ranked skill trends from ordered weekly frequency maps.

        ``weekly_counts`` must be ordered oldest to newest. The last entry is the
        current period, the second-to-last is the previous period, and all prior
        periods contribute to historical mean and standard deviation.
        """
        if not weekly_counts:
            return TrendModelResult(
                model_version=self.model_version,
                generated_at=datetime.now(timezone.utc),
                period_count=0,
                skills=(),
            )

        current_counts = dict(weekly_counts[-1])
        previous_counts = dict(weekly_counts[-2]) if len(weekly_counts) >= 2 else {}
        historical_periods = weekly_counts[:-1]

        all_skills = set(current_counts)
        for period in weekly_counts:
            all_skills.update(period.keys())

        scores: list[SkillTrendScore] = []
        for skill in sorted(all_skills):
            current = int(current_counts.get(skill, 0))
            previous = int(previous_counts.get(skill, 0))
            change = current - previous
            change_percent = _change_percent(current, previous)

            history_values = [
                int(period.get(skill, 0)) for period in historical_periods
            ]
            historical_mean, historical_std = _historical_stats(history_values)
            z_score = _compute_z_score(
                current=current,
                historical_mean=historical_mean,
                historical_std=historical_std,
                history_count=len(history_values),
                min_history_periods=self.min_history_periods,
            )
            trend, direction = _classify_trend(
                z_score=z_score,
                change=change,
                history_count=len(history_values),
                min_history_periods=self.min_history_periods,
                rising_threshold=self.z_rising_threshold,
                falling_threshold=self.z_falling_threshold,
            )

            scores.append(
                SkillTrendScore(
                    skill=skill,
                    current_mentions=current,
                    previous_mentions=previous,
                    change=change,
                    change_percent=change_percent,
                    historical_mean=historical_mean,
                    historical_std=historical_std,
                    z_score=z_score,
                    trend=trend,
                    direction=direction,
                )
            )

        ranked = tuple(sorted(scores, key=self._rank_key))
        return TrendModelResult(
            model_version=self.model_version,
            generated_at=datetime.now(timezone.utc),
            period_count=len(weekly_counts),
            skills=ranked,
        )

    def _rank_key(self, score: SkillTrendScore) -> tuple:
        z_rank = score.z_score if score.z_score is not None else float("-inf")
        change_rank = score.change_percent if score.change_percent is not None else float("-inf")
        return (-z_rank, -change_rank, score.skill)
