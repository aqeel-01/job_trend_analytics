"""FastAPI route handlers for the V1 trend API."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from pipeline import __version__
from pipeline.api.dependencies import compute_trend, get_database, get_trend_model
from pipeline.api.schemas import (
    HealthResponse,
    ModelInfoResponse,
    SkillDetailResponse,
    SkillTrendResponse,
    TrendingSkillsResponse,
)
from pipeline.storage.database import Database
from pipeline.trend.model import TrendModel
from pipeline.trend.models import SkillTrendScore, TrendModelResult

logger = logging.getLogger(__name__)

router = APIRouter()


def _to_skill_response(score: SkillTrendScore) -> SkillTrendResponse:
    return SkillTrendResponse(
        skill=score.skill,
        current_mentions=score.current_mentions,
        previous_mentions=score.previous_mentions,
        change=score.change,
        change_percent=score.change_percent,
        historical_mean=score.historical_mean,
        historical_std=score.historical_std,
        z_score=score.z_score,
        trend=score.trend.value,
        direction=score.direction.value,
    )


def _get_result(db: Database, model: TrendModel) -> TrendModelResult:
    try:
        return compute_trend(db, model)
    except Exception as exc:
        logger.exception("Trend computation failed: %s", exc)
        raise HTTPException(
            status_code=500, detail="Trend model computation failed"
        ) from exc


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Liveness check."""
    return HealthResponse(status="ok", version=__version__)


@router.get("/model-info", response_model=ModelInfoResponse, tags=["system"])
def model_info(
    model: Annotated[TrendModel, Depends(get_trend_model)],
) -> ModelInfoResponse:
    """Return the active model version and configuration."""
    return ModelInfoResponse(
        model_version=model.model_version,
        method="z_score",
        min_history_periods=model.min_history_periods,
        z_rising_threshold=model.z_rising_threshold,
        z_falling_threshold=model.z_falling_threshold,
    )


@router.get(
    "/trending-skills",
    response_model=TrendingSkillsResponse,
    tags=["trends"],
)
def trending_skills(
    model: Annotated[TrendModel, Depends(get_trend_model)],
    db: Annotated[Database, Depends(get_database)],
    limit: Annotated[
        int,
        Query(ge=1, le=200, description="Maximum number of skills to return"),
    ] = 10,
    direction: Annotated[
        str | None,
        Query(
            pattern="^(up|down|flat|unknown)$",
            description="Filter by trend direction",
        ),
    ] = None,
) -> TrendingSkillsResponse:
    """Return skills ranked by trend score (z-score, then change_percent)."""
    result = _get_result(db, model)

    filtered = list(result.skills)
    if direction is not None:
        filtered = [s for s in filtered if s.direction.value == direction]

    return TrendingSkillsResponse(
        model_version=result.model_version,
        generated_at=result.generated_at,
        period_count=result.period_count,
        limit=limit,
        total_skills=len(filtered),
        skills=[_to_skill_response(s) for s in filtered[:limit]],
    )


@router.get(
    "/skills/{skill_name}",
    response_model=SkillDetailResponse,
    tags=["trends"],
)
def skill_detail(
    skill_name: str,
    model: Annotated[TrendModel, Depends(get_trend_model)],
    db: Annotated[Database, Depends(get_database)],
) -> SkillDetailResponse:
    """Return trend data for a single named skill (case-insensitive lookup)."""
    result = _get_result(db, model)

    match = next(
        (s for s in result.skills if s.skill.lower() == skill_name.lower()),
        None,
    )

    return SkillDetailResponse(
        skill=skill_name,
        found=match is not None,
        model_version=result.model_version,
        generated_at=result.generated_at,
        data=_to_skill_response(match) if match is not None else None,
    )
