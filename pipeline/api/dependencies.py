"""FastAPI dependency providers for the V1 API."""

import time
from functools import lru_cache

from pipeline.config.settings import get_settings
from pipeline.monitoring.recorder import record_model_execution_time
from pipeline.storage.database import Database
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
    """
    Aggregate job_skills into per-ISO-week skill mention frequencies.

    Queries join job_skills → skills → jobs, grouping by the
    year-week (strftime '%Y-%W') of each job's ingestion timestamp.
    """
    conn = database.connect()
    rows = conn.execute(
        """
        SELECT
            strftime('%Y-%W', j.ingested_at) AS week,
            s.canonical_name                  AS skill,
            COUNT(*)                          AS cnt
        FROM job_skills js
        JOIN jobs   j ON js.job_id   = j.id
        JOIN skills s ON js.skill_id = s.id
        GROUP BY week, s.canonical_name
        ORDER BY week ASC
        """
    ).fetchall()

    weeks: dict[str, dict[str, int]] = {}
    for row in rows:
        week = row["week"]
        skill = row["skill"]
        cnt = int(row["cnt"])
        weeks.setdefault(week, {})[skill] = cnt

    return [counts for counts in weeks.values()]


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
