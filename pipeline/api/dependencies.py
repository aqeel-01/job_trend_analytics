"""FastAPI dependency providers for the V1 API."""

import time
from functools import lru_cache

from pipeline.config.settings import get_settings
from pipeline.monitoring.recorder import record_model_execution_time
from pipeline.storage.database import Database
from pipeline.trend.data import load_weekly_counts
from pipeline.trend.model import TrendModel
from pipeline.trend.models import TrendModelResult


@lru_cache(maxsize=1)
def _get_cached_database() -> Database:
    settings = get_settings()
    db = Database(settings.database_path)
    db.initialize()
    return db


def get_database() -> Database:
    """Dependency: return the shared, initialized database connection."""
    return _get_cached_database()


def get_trend_model() -> TrendModel:
    """Dependency: return the configured V1 trend model."""
    return TrendModel()


def _load_weekly_counts(database: Database) -> list[dict[str, int]]:
    """Aggregate job_skills into per-ISO-week skill mention frequencies."""
    return load_weekly_counts(database)


def compute_trend(database: Database, model: TrendModel) -> TrendModelResult:
    """Load weekly counts from DB and run the trend model."""
    weekly = _load_weekly_counts(database)
    started = time.monotonic()
    try:
        result = model.compute(weekly)
        record_model_execution_time(
            duration_seconds=time.monotonic() - started,
            success=True,
            model_version=result.model_version,
        )
        return result
    except Exception as exc:
        record_model_execution_time(
            duration_seconds=time.monotonic() - started,
            success=False,
            detail=str(exc),
        )
        raise
