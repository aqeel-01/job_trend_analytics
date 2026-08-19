"""V1 model evaluation comparing trend model against frequency baseline."""

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

from pipeline.evaluation.baseline import FrequencyBaseline
from pipeline.evaluation.models import (
    ChangeDetectionMetric,
    DatasetLimitation,
    EvaluationReport,
    HistoricalValidationMetric,
    RankingStabilityMetric,
    TopKOverlapMetric,
)
from pipeline.trend.model import TrendModel
from pipeline.trend.models import TrendLabel


def _rank_correlation(
    ranking_a: list[str],
    ranking_b: list[str],
) -> tuple[float | None, float | None]:
    """Compute Kendall tau-b and Spearman rho for two skill rankings."""
    if len(ranking_a) < 2 or len(ranking_b) < 2:
        return None, None

    all_skills = sorted(set(ranking_a) | set(ranking_b))
    if len(all_skills) < 2:
        return None, None

    rank_a = {skill: idx for idx, skill in enumerate(ranking_a)}
    rank_b = {skill: idx for idx, skill in enumerate(ranking_b)}

    max_rank_a = len(ranking_a)
    max_rank_b = len(ranking_b)

    a_ranks = [rank_a.get(skill, max_rank_a) for skill in all_skills]
    b_ranks = [rank_b.get(skill, max_rank_b) for skill in all_skills]

    n = len(all_skills)

    # Spearman rho
    d_squared = sum((a - b) ** 2 for a, b in zip(a_ranks, b_ranks))
    if n * (n**2 - 1) == 0:
        spearman = None
    else:
        spearman = 1 - (6 * d_squared) / (n * (n**2 - 1))

    # Kendall tau-b
    concordant = 0
    discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            a_diff = a_ranks[i] - a_ranks[j]
            b_diff = b_ranks[i] - b_ranks[j]
            product = a_diff * b_diff
            if product > 0:
                concordant += 1
            elif product < 0:
                discordant += 1

    total_pairs = concordant + discordant
    kendall = (concordant - discordant) / total_pairs if total_pairs > 0 else None

    return kendall, spearman


def _top_k_overlap(
    ranking_a: list[str],
    ranking_b: list[str],
    k: int,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], float]:
    """Compute top-k overlap between two rankings."""
    top_a = tuple(ranking_a[:k])
    top_b = tuple(ranking_b[:k])
    overlap = tuple(sorted(set(top_a) & set(top_b)))
    max_len = max(len(top_a), len(top_b), 1)
    ratio = len(overlap) / max_len
    return top_a, top_b, overlap, ratio


def _historical_validation(
    weekly_counts: Sequence[Mapping[str, int]],
    model: TrendModel,
    k: int,
) -> tuple[int, float | None]:
    """Hold-out last period and check if top-rising skills keep rising."""
    if len(weekly_counts) < 4:
        return 0, None

    holdout_periods = list(weekly_counts[:-1])
    actual_current = dict(weekly_counts[-1])

    predicted_result = model.compute(holdout_periods)
    predicted_rising = [
        score.skill
        for score in predicted_result.skills
        if score.trend == TrendLabel.RISING
    ][:k]

    if not predicted_rising:
        return 1, None

    previous = dict(weekly_counts[-2])
    hits = 0
    for skill in predicted_rising:
        actual = int(actual_current.get(skill, 0))
        prev = int(previous.get(skill, 0))
        if actual >= prev:
            hits += 1

    hit_rate = hits / len(predicted_rising)
    return 1, hit_rate


class ModelEvaluator:
    """Compare V1 trend model with frequency baseline per SRS requirements."""

    def __init__(
        self,
        model: TrendModel | None = None,
        baseline: FrequencyBaseline | None = None,
        top_k: int = 5,
    ) -> None:
        self.model = model or TrendModel()
        self.baseline = baseline or FrequencyBaseline()
        self.top_k = top_k

    def evaluate(
        self,
        weekly_counts: Sequence[Mapping[str, int]],
    ) -> EvaluationReport:
        """Run full evaluation and return structured report."""
        trend_result = self.model.compute(weekly_counts)
        baseline_scores = self.baseline.compute(weekly_counts)

        trend_ranking = [score.skill for score in trend_result.skills]
        baseline_ranking = [score.skill for score in baseline_scores]

        # Ranking stability
        kendall, spearman = _rank_correlation(trend_ranking, baseline_ranking)
        ranking_stability = RankingStabilityMetric(
            kendall_tau=_round(kendall),
            spearman_rho=_round(spearman),
            description=(
                "Correlation between trend model ranking (by z-score) and "
                "frequency baseline ranking (by raw count). High correlation "
                "means the trend model agrees with simple frequency ordering."
            ),
        )

        # Top-k overlap
        top_a, top_b, overlap, ratio = _top_k_overlap(
            trend_ranking, baseline_ranking, self.top_k,
        )
        top_k_overlap = TopKOverlapMetric(
            k=self.top_k,
            trend_model_top_k=top_a,
            baseline_top_k=top_b,
            overlap=overlap,
            overlap_ratio=_round(ratio),
            description=(
                f"Overlap in top-{self.top_k} skills between the trend model "
                f"and frequency baseline. Low overlap indicates the z-score "
                f"model surfaces different insights than simple counting."
            ),
        )

        # Change detection
        rising = sum(1 for s in trend_result.skills if s.trend == TrendLabel.RISING)
        falling = sum(1 for s in trend_result.skills if s.trend == TrendLabel.FALLING)
        stable = sum(1 for s in trend_result.skills if s.trend == TrendLabel.STABLE)
        insufficient = sum(
            1 for s in trend_result.skills
            if s.trend == TrendLabel.INSUFFICIENT_DATA
        )
        has_z = sum(1 for s in trend_result.skills if s.z_score is not None)
        change_detection = ChangeDetectionMetric(
            skills_with_z_score=has_z,
            rising_detected=rising,
            falling_detected=falling,
            stable_detected=stable,
            insufficient_data=insufficient,
            description=(
                "Distribution of trend labels from the z-score model. "
                "Skills with insufficient history cannot be classified."
            ),
        )

        # Historical validation
        periods_evaluated, hit_rate = _historical_validation(
            weekly_counts, self.model, self.top_k,
        )
        historical_validation = HistoricalValidationMetric(
            periods_evaluated=periods_evaluated,
            hit_rate_at_k=_round(hit_rate),
            k=self.top_k,
            description=(
                f"Hold-out validation: predicted top-{self.top_k} rising skills "
                f"from historical data, then checked if they continued rising "
                f"in the held-out period."
            ),
        )

        # Limitations
        limitations = self._assess_limitations(
            weekly_counts, trend_result, insufficient,
        )

        return EvaluationReport(
            generated_at=datetime.now(timezone.utc),
            trend_model_version=self.model.model_version,
            baseline_name=self.baseline.name,
            period_count=len(weekly_counts),
            skill_count=len(trend_result.skills),
            ranking_stability=ranking_stability,
            top_k_overlap=top_k_overlap,
            change_detection=change_detection,
            historical_validation=historical_validation,
            limitations=tuple(limitations),
        )

    def _assess_limitations(
        self,
        weekly_counts: Sequence[Mapping[str, int]],
        trend_result,
        insufficient_count: int,
    ) -> list[DatasetLimitation]:
        limitations: list[DatasetLimitation] = []

        if len(weekly_counts) < 4:
            limitations.append(
                DatasetLimitation(
                    code="SMALL_PERIOD_COUNT",
                    message=(
                        f"Only {len(weekly_counts)} weekly period(s) available. "
                        f"At least 4 are recommended for reliable z-score "
                        f"computation and historical validation."
                    ),
                    severity="high",
                ),
            )

        if len(weekly_counts) < self.model.min_history_periods + 1:
            limitations.append(
                DatasetLimitation(
                    code="INSUFFICIENT_HISTORY",
                    message=(
                        f"Fewer than {self.model.min_history_periods + 1} "
                        f"periods means z-scores cannot be computed for any skill."
                    ),
                    severity="critical",
                ),
            )

        if insufficient_count > 0:
            ratio = insufficient_count / max(len(trend_result.skills), 1) * 100
            limitations.append(
                DatasetLimitation(
                    code="PARTIAL_Z_SCORES",
                    message=(
                        f"{insufficient_count} of {len(trend_result.skills)} "
                        f"skills ({ratio:.0f}%) have insufficient historical "
                        f"data for z-score computation."
                    ),
                    severity="medium" if ratio < 50 else "high",
                ),
            )

        all_skills: set[str] = set()
        for period in weekly_counts:
            all_skills.update(period.keys())
        if len(all_skills) < 10:
            limitations.append(
                DatasetLimitation(
                    code="LOW_SKILL_DIVERSITY",
                    message=(
                        f"Only {len(all_skills)} distinct skills observed. "
                        f"Trend rankings are less meaningful with very few skills."
                    ),
                    severity="medium",
                ),
            )

        limitations.append(
            DatasetLimitation(
                code="V1_GENERAL_DISCLAIMER",
                message=(
                    "V1 uses a statistical z-score model on a small dataset. "
                    "Results should be interpreted as directional signals, not "
                    "definitive market analysis."
                ),
                severity="info",
            ),
        )

        return limitations


def _round(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(value, digits)
