"""Tests for the V1 statistical trend model."""

from pipeline.trend.model import TrendModel
from pipeline.trend.models import TrendDirection, TrendLabel


def _skill(result, name: str):
    return next(item for item in result.skills if item.skill == name)


def test_rising_skill_with_clear_z_score() -> None:
    weekly = [
        {"Kubernetes": 10, "Python": 20},
        {"Kubernetes": 12, "Python": 22},
        {"Kubernetes": 14, "Python": 24},
        {"Kubernetes": 31, "Python": 25},
    ]
    result = TrendModel().compute(weekly)
    kubernetes = _skill(result, "Kubernetes")

    assert kubernetes.current_mentions == 31
    assert kubernetes.previous_mentions == 14
    assert kubernetes.change == 17
    assert kubernetes.change_percent == (17 / 14) * 100
    assert kubernetes.historical_mean is not None
    assert kubernetes.historical_std is not None
    assert kubernetes.z_score is not None
    assert kubernetes.z_score > 0
    assert kubernetes.trend == TrendLabel.RISING
    assert kubernetes.direction == TrendDirection.UP


def test_falling_skill() -> None:
    weekly = [
        {"Docker": 30},
        {"Docker": 25},
        {"Docker": 20},
        {"Docker": 10},
    ]
    docker = _skill(TrendModel().compute(weekly), "Docker")

    assert docker.change == -10
    assert docker.z_score is not None
    assert docker.z_score < 0
    assert docker.trend == TrendLabel.FALLING
    assert docker.direction == TrendDirection.DOWN


def test_stable_skill() -> None:
    weekly = [
        {"SQL": 10},
        {"SQL": 10},
        {"SQL": 10},
        {"SQL": 10},
    ]
    sql = _skill(TrendModel().compute(weekly), "SQL")

    assert sql.z_score == 0.0
    assert sql.historical_std == 0.0
    assert sql.trend == TrendLabel.STABLE
    assert sql.direction == TrendDirection.FLAT


def test_zero_std_with_changed_current() -> None:
    weekly = [
        {"Rust": 5},
        {"Rust": 5},
        {"Rust": 5},
        {"Rust": 8},
    ]
    rust = _skill(TrendModel().compute(weekly), "Rust")

    assert rust.historical_std == 0.0
    assert rust.z_score == 1.0
    assert rust.trend == TrendLabel.RISING


def test_insufficient_historical_data() -> None:
    weekly = [{"Go": 3}, {"Go": 5}]
    go = _skill(TrendModel().compute(weekly), "Go")

    assert go.z_score is None
    assert go.trend == TrendLabel.INSUFFICIENT_DATA
    assert go.direction == TrendDirection.UNKNOWN


def test_previous_zero_change_percent_none() -> None:
    weekly = [
        {"Kafka": 0},
        {"Kafka": 0},
        {"Kafka": 5},
    ]
    kafka = _skill(TrendModel().compute(weekly), "Kafka")

    assert kafka.current_mentions == 5
    assert kafka.previous_mentions == 0
    assert kafka.change_percent is None


def test_skills_ranked_by_z_score() -> None:
    weekly = [
        {"Alpha": 5, "Beta": 5},
        {"Alpha": 5, "Beta": 5},
        {"Alpha": 5, "Beta": 5},
        {"Alpha": 25, "Beta": 5},
    ]
    result = TrendModel().compute(weekly)

    assert result.skills[0].skill == "Alpha"
    assert result.skills[0].z_score == 1.0
    assert result.skills[1].z_score == 0.0


def test_empty_input_returns_empty_result() -> None:
    result = TrendModel().compute([])

    assert result.period_count == 0
    assert result.skills == ()
