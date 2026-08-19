"""Tests for the V1 model evaluation framework."""

import json

from pipeline.evaluation.baseline import FrequencyBaseline
from pipeline.evaluation.evaluator import ModelEvaluator
from pipeline.evaluation.models import EvaluationReport
from pipeline.trend.model import TrendModel
from pipeline.trend.models import TrendLabel


# ─── deterministic synthetic dataset ────────────────────────────────────────

WEEKLY = [
    {"Python": 20, "Docker": 10, "Kubernetes": 5, "Rust": 1, "SQL": 15},
    {"Python": 22, "Docker": 12, "Kubernetes": 7, "Rust": 2, "SQL": 14},
    {"Python": 24, "Docker": 11, "Kubernetes": 10, "Rust": 3, "SQL": 13},
    {"Python": 25, "Docker": 10, "Kubernetes": 20, "Rust": 4, "SQL": 12},
]


# ─── baseline tests ────────────────────────────────────────────────────────

def test_frequency_baseline_ranks_by_count() -> None:
    baseline = FrequencyBaseline()
    scores = baseline.compute(WEEKLY)

    names = [score.skill for score in scores]
    assert names[0] == "Python"
    assert scores[0].current_mentions == 25
    assert len(scores) == 5


def test_frequency_baseline_empty() -> None:
    assert FrequencyBaseline().compute([]) == []


# ─── ranking stability ─────────────────────────────────────────────────────

def test_ranking_stability_computed() -> None:
    report = ModelEvaluator().evaluate(WEEKLY)

    assert report.ranking_stability.kendall_tau is not None
    assert report.ranking_stability.spearman_rho is not None
    assert -1.0 <= report.ranking_stability.kendall_tau <= 1.0
    assert -1.0 <= report.ranking_stability.spearman_rho <= 1.0


# ─── top-k overlap ─────────────────────────────────────────────────────────

def test_top_k_overlap() -> None:
    report = ModelEvaluator(top_k=3).evaluate(WEEKLY)

    assert report.top_k_overlap.k == 3
    assert len(report.top_k_overlap.trend_model_top_k) == 3
    assert len(report.top_k_overlap.baseline_top_k) == 3
    assert 0.0 <= report.top_k_overlap.overlap_ratio <= 1.0


def test_top_k_overlap_with_identical_rankings() -> None:
    flat_data = [
        {"A": 10, "B": 5},
        {"A": 10, "B": 5},
        {"A": 10, "B": 5},
    ]
    report = ModelEvaluator(top_k=2).evaluate(flat_data)

    assert report.top_k_overlap.overlap_ratio == 1.0


# ─── change detection ──────────────────────────────────────────────────────

def test_change_detection_counts() -> None:
    report = ModelEvaluator().evaluate(WEEKLY)
    cd = report.change_detection

    assert cd.skills_with_z_score > 0
    total = cd.rising_detected + cd.falling_detected + cd.stable_detected + cd.insufficient_data
    assert total == 5
    assert cd.rising_detected >= 1


def test_change_detection_identifies_kubernetes_as_rising() -> None:
    trend_result = TrendModel().compute(WEEKLY)
    kubernetes = next(s for s in trend_result.skills if s.skill == "Kubernetes")

    assert kubernetes.trend == TrendLabel.RISING


# ─── historical validation ─────────────────────────────────────────────────

def test_historical_validation_with_sufficient_data() -> None:
    report = ModelEvaluator(top_k=3).evaluate(WEEKLY)

    assert report.historical_validation.periods_evaluated == 1
    assert report.historical_validation.hit_rate_at_k is not None
    assert 0.0 <= report.historical_validation.hit_rate_at_k <= 1.0


def test_historical_validation_insufficient_periods() -> None:
    short_data = [{"A": 5}, {"A": 10}]
    report = ModelEvaluator().evaluate(short_data)

    assert report.historical_validation.periods_evaluated == 0
    assert report.historical_validation.hit_rate_at_k is None


# ─── limitations ────────────────────────────────────────────────────────────

def test_limitations_reported_for_small_dataset() -> None:
    small = [{"Go": 3}, {"Go": 5}]
    report = ModelEvaluator().evaluate(small)

    codes = {lim.code for lim in report.limitations}
    assert "SMALL_PERIOD_COUNT" in codes
    assert "V1_GENERAL_DISCLAIMER" in codes


def test_limitations_include_insufficient_z_scores() -> None:
    two_periods = [{"Python": 10}, {"Python": 12}]
    report = ModelEvaluator().evaluate(two_periods)

    codes = {lim.code for lim in report.limitations}
    assert "PARTIAL_Z_SCORES" in codes


def test_limitations_include_low_skill_diversity() -> None:
    report = ModelEvaluator().evaluate([{"A": 1}, {"A": 2}, {"A": 3}])

    codes = {lim.code for lim in report.limitations}
    assert "LOW_SKILL_DIVERSITY" in codes


# ─── serialization ──────────────────────────────────────────────────────────

def test_report_serializes_to_json() -> None:
    report = ModelEvaluator().evaluate(WEEKLY)
    report_dict = report.to_dict()

    json_str = json.dumps(report_dict, indent=2)
    assert '"trend_model_version"' in json_str
    assert '"ranking_stability"' in json_str
    assert '"limitations"' in json_str

    parsed = json.loads(json_str)
    assert isinstance(parsed["limitations"], list)
    assert parsed["period_count"] == 4
    assert parsed["skill_count"] == 5


# ─── edge cases ─────────────────────────────────────────────────────────────

def test_evaluation_with_empty_data() -> None:
    report = ModelEvaluator().evaluate([])

    assert report.period_count == 0
    assert report.skill_count == 0
    assert report.ranking_stability.kendall_tau is None


def test_evaluation_with_single_period() -> None:
    report = ModelEvaluator().evaluate([{"X": 5}])

    assert report.period_count == 1
    assert report.skill_count == 1
    assert report.change_detection.insufficient_data == 1
