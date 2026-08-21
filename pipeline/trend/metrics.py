"""Shared evaluation-metric helpers for trend model runs."""

from __future__ import annotations

from typing import Any

from pipeline.trend.models import TrendModelResult


def build_evaluation_metrics(result: TrendModelResult, top_k: int = 10) -> dict[str, Any]:
    """Build evaluation/metrics payload stored with each model run."""
    return {
        "skills_ranked": len(result.skills),
        "rising_skills": sum(1 for s in result.skills if s.trend.value == "rising"),
        "falling_skills": sum(1 for s in result.skills if s.trend.value == "falling"),
        "stable_skills": sum(1 for s in result.skills if s.trend.value == "stable"),
        "insufficient_data_skills": sum(
            1 for s in result.skills if s.trend.value == "insufficient_data"
        ),
        "period_count": result.period_count,
        "top_skills": [s.skill for s in result.skills[:top_k]],
    }
