"""Compare persisted V1 model runs / rankings."""

from __future__ import annotations

import json
from typing import Any

from pipeline.retraining.models import ModelVersionComparison, SkillRankingDelta
from pipeline.storage.models import StoredModelRun
from pipeline.trend.models import TrendModelResult


def _parse_json_field(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _top_skills_from_metrics(metrics: dict[str, Any], k: int) -> list[str]:
    top = metrics.get("top_skills") or []
    if not isinstance(top, list):
        return []
    return [str(skill) for skill in top[:k]]


def _top_skills_from_result(result: TrendModelResult | None, k: int) -> list[str]:
    if result is None:
        return []
    return [score.skill for score in result.skills[:k]]


def _metric_deltas(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    keys = sorted(set(previous) | set(current))
    deltas: dict[str, Any] = {}
    for key in keys:
        if key == "top_skills":
            continue
        prev_val = previous.get(key)
        curr_val = current.get(key)
        if isinstance(prev_val, (int, float)) and isinstance(curr_val, (int, float)):
            deltas[key] = curr_val - prev_val
        else:
            deltas[key] = {"previous": prev_val, "current": curr_val}
    return deltas


def _ranking_deltas(previous: list[str], current: list[str]) -> list[SkillRankingDelta]:
    prev_rank = {skill: idx + 1 for idx, skill in enumerate(previous)}
    curr_rank = {skill: idx + 1 for idx, skill in enumerate(current)}
    skills = sorted(set(prev_rank) | set(curr_rank))
    deltas: list[SkillRankingDelta] = []
    for skill in skills:
        p = prev_rank.get(skill)
        c = curr_rank.get(skill)
        change = None if p is None or c is None else p - c  # positive = improved rank
        deltas.append(
            SkillRankingDelta(
                skill=skill,
                previous_rank=p,
                current_rank=c,
                rank_change=change,
            )
        )
    # Prefer skills that changed rank, then alphabetical.
    deltas.sort(
        key=lambda d: (
            0 if d.rank_change not in (None, 0) else 1,
            -(abs(d.rank_change) if d.rank_change is not None else 0),
            d.skill,
        )
    )
    return deltas


def compare_model_runs(
    previous: StoredModelRun,
    current: StoredModelRun,
    *,
    previous_result: TrendModelResult | None = None,
    current_result: TrendModelResult | None = None,
    top_k: int = 10,
) -> ModelVersionComparison:
    """Compare two model-run metadata records (and optional live results)."""
    prev_metrics = _parse_json_field(previous.evaluation_metrics)
    curr_metrics = _parse_json_field(current.evaluation_metrics)

    previous_top = _top_skills_from_result(previous_result, top_k) or _top_skills_from_metrics(
        prev_metrics, top_k
    )
    current_top = _top_skills_from_result(current_result, top_k) or _top_skills_from_metrics(
        curr_metrics, top_k
    )

    overlap = sorted(set(previous_top) & set(current_top))
    denom = max(len(previous_top), len(current_top), 1)
    overlap_ratio = len(overlap) / denom

    prev_size = previous.training_dataset_size
    curr_size = current.training_dataset_size
    size_delta = None
    if prev_size is not None and curr_size is not None:
        size_delta = curr_size - prev_size

    metric_deltas = _metric_deltas(prev_metrics, curr_metrics)
    ranking_deltas = _ranking_deltas(previous_top, current_top)

    summary_parts = [
        f"{previous.model_version} → {current.model_version}",
        f"top-{top_k} overlap={len(overlap)}/{denom} ({overlap_ratio:.0%})",
    ]
    if size_delta is not None:
        summary_parts.append(f"dataset_size_delta={size_delta:+d}")
    if "rising_skills" in metric_deltas and isinstance(metric_deltas["rising_skills"], (int, float)):
        summary_parts.append(f"rising_skills_delta={metric_deltas['rising_skills']:+g}")

    return ModelVersionComparison(
        previous_version=previous.model_version,
        current_version=current.model_version,
        previous_run_id=previous.id,
        current_run_id=current.id,
        previous_trained_at=previous.trained_at,
        current_trained_at=current.trained_at,
        previous_dataset_size=prev_size,
        current_dataset_size=curr_size,
        dataset_size_delta=size_delta,
        previous_metrics=prev_metrics,
        current_metrics=curr_metrics,
        metric_deltas=metric_deltas,
        top_k=top_k,
        previous_top_skills=previous_top,
        current_top_skills=current_top,
        top_k_overlap=overlap,
        top_k_overlap_ratio=overlap_ratio,
        ranking_deltas=ranking_deltas,
        summary="; ".join(summary_parts),
    )
