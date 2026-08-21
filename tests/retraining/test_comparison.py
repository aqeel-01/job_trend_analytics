"""Tests for model-version comparison."""

import json
from datetime import datetime, timezone

import pytest

from pipeline.retraining.comparison import compare_model_runs
from pipeline.storage.models import StoredModelRun


def _run(
    *,
    run_id: int,
    version: str,
    size: int,
    metrics: dict,
    trained_at: datetime | None = None,
) -> StoredModelRun:
    return StoredModelRun(
        id=run_id,
        model_version=version,
        trained_at=trained_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
        training_dataset_size=size,
        model_parameters=json.dumps({"method": "z_score"}),
        evaluation_metrics=json.dumps(metrics),
        status="completed",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_compare_versions_overlap_and_deltas() -> None:
    previous = _run(
        run_id=1,
        version="v1.0",
        size=100,
        metrics={
            "skills_ranked": 3,
            "rising_skills": 1,
            "falling_skills": 1,
            "top_skills": ["Python", "Java", "Go"],
        },
    )
    current = _run(
        run_id=2,
        version="v1.1",
        size=150,
        metrics={
            "skills_ranked": 4,
            "rising_skills": 2,
            "falling_skills": 1,
            "top_skills": ["Python", "Rust", "Go"],
        },
        trained_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )

    comparison = compare_model_runs(previous, current, top_k=3)

    assert comparison.previous_version == "v1.0"
    assert comparison.current_version == "v1.1"
    assert comparison.dataset_size_delta == 50
    assert comparison.metric_deltas["rising_skills"] == 1
    assert comparison.top_k_overlap == ["Go", "Python"]
    assert comparison.top_k_overlap_ratio == pytest.approx(2 / 3)
    assert any(d.skill == "Rust" and d.previous_rank is None for d in comparison.ranking_deltas)
