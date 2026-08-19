"""Shared fixtures for API tests.

Routes are exercised via FastAPI's TestClient.  The database and
compute_trend function are replaced via pytest monkeypatching so tests
never touch SQLite and run fully deterministically.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from pipeline.api.app import create_app
from pipeline.api import dependencies as dep_module
from pipeline.trend.model import TrendModel
from pipeline.trend.models import (
    SkillTrendScore,
    TrendDirection,
    TrendLabel,
    TrendModelResult,
)

MOCK_RESULT = TrendModelResult(
    model_version="v1.0",
    generated_at=datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc),
    period_count=4,
    skills=(
        SkillTrendScore(
            skill="Kubernetes",
            current_mentions=47,
            previous_mentions=31,
            change=16,
            change_percent=51.6,
            historical_mean=25.0,
            historical_std=8.2,
            z_score=2.68,
            trend=TrendLabel.RISING,
            direction=TrendDirection.UP,
        ),
        SkillTrendScore(
            skill="Python",
            current_mentions=120,
            previous_mentions=115,
            change=5,
            change_percent=4.35,
            historical_mean=112.0,
            historical_std=6.5,
            z_score=1.23,
            trend=TrendLabel.RISING,
            direction=TrendDirection.UP,
        ),
        SkillTrendScore(
            skill="Docker",
            current_mentions=30,
            previous_mentions=32,
            change=-2,
            change_percent=-6.25,
            historical_mean=33.0,
            historical_std=2.0,
            z_score=-1.5,
            trend=TrendLabel.FALLING,
            direction=TrendDirection.DOWN,
        ),
        SkillTrendScore(
            skill="SQL",
            current_mentions=20,
            previous_mentions=20,
            change=0,
            change_percent=0.0,
            historical_mean=20.0,
            historical_std=0.0,
            z_score=0.0,
            trend=TrendLabel.STABLE,
            direction=TrendDirection.FLAT,
        ),
    ),
)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """TestClient with dependency and compute_trend overrides."""
    # Patch compute_trend on every module that imports it by reference
    monkeypatch.setattr(dep_module, "compute_trend", lambda db, model: MOCK_RESULT)

    import pipeline.api.routes as routes_module
    monkeypatch.setattr(routes_module, "compute_trend", lambda db, model: MOCK_RESULT)

    app = create_app()
    mock_db = MagicMock()

    app.dependency_overrides[dep_module.get_database] = lambda: mock_db
    app.dependency_overrides[dep_module.get_trend_model] = lambda: TrendModel(model_version="v1.0")

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
