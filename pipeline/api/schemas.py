"""Pydantic response schemas for the V1 REST API."""

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
    version: str = Field(..., examples=["0.1.0"])


class ModelInfoResponse(BaseModel):
    model_version: str = Field(..., examples=["v1.0"])
    method: str = Field(..., examples=["z_score"])
    min_history_periods: int
    z_rising_threshold: float
    z_falling_threshold: float


class SkillTrendResponse(BaseModel):
    skill: str
    current_mentions: int
    previous_mentions: int
    change: int
    change_percent: float | None
    historical_mean: float | None
    historical_std: float | None
    z_score: float | None
    trend: str
    direction: str


class TrendingSkillsResponse(BaseModel):
    model_version: str
    generated_at: datetime
    period_count: int
    limit: int
    total_skills: int
    skills: list[SkillTrendResponse]


class SkillDetailResponse(BaseModel):
    skill: str
    found: bool
    model_version: str
    generated_at: datetime
    data: SkillTrendResponse | None = None
