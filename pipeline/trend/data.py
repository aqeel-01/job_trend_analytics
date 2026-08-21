"""Load weekly skill-count datasets for trend training/retraining."""

from __future__ import annotations

from datetime import datetime

from pipeline.storage.database import Database
from pipeline.storage.repositories import JobRepository, ModelRunRepository


def load_weekly_counts(database: Database) -> list[dict[str, int]]:
    """
    Aggregate job_skills into per-ISO-week skill mention frequencies.

    Returns a list of period maps ordered oldest → newest.
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


def dataset_fingerprint(weekly_counts: list[dict[str, int]]) -> dict:
    """Summarize a weekly dataset for new-data detection and metadata."""
    period_count = len(weekly_counts)
    skill_names: set[str] = set()
    total_mentions = 0
    for period in weekly_counts:
        skill_names.update(period.keys())
        total_mentions += sum(int(v) for v in period.values())
    return {
        "period_count": period_count,
        "unique_skills": len(skill_names),
        "total_mentions": total_mentions,
    }


def detect_new_data(
    database: Database,
    model_run_repository: ModelRunRepository | None = None,
    weekly_counts: list[dict[str, int]] | None = None,
) -> dict:
    """
    Detect whether the current job-skill dataset has grown since the last model run.

    Returns a dict with:
        has_new_data (bool), reason (str), current (dict), previous (dict|None),
        latest_model_version (str|None), job_count (int).
    """
    repo = model_run_repository or ModelRunRepository(database)
    weekly = weekly_counts if weekly_counts is not None else load_weekly_counts(database)
    current = dataset_fingerprint(weekly)
    job_count = JobRepository(database).count_jobs()
    latest = repo.get_latest()

    if latest is None:
        return {
            "has_new_data": current["period_count"] > 0,
            "reason": "no_previous_model_run",
            "current": current,
            "previous": None,
            "latest_model_version": None,
            "job_count": job_count,
        }

    previous = {
        "training_dataset_size": latest.training_dataset_size,
        "model_version": latest.model_version,
        "trained_at": latest.trained_at.isoformat() if latest.trained_at else None,
    }

    # Prefer period growth; also treat larger mention totals as new data.
    prev_size = latest.training_dataset_size or 0
    has_growth = current["total_mentions"] > prev_size
    if has_growth:
        reason = "dataset_grew"
    else:
        reason = "no_growth_since_last_train"

    return {
        "has_new_data": has_growth,
        "reason": reason,
        "current": current,
        "previous": previous,
        "latest_model_version": latest.model_version,
        "job_count": job_count,
    }


def latest_job_ingested_at(database: Database) -> datetime | None:
    """Return the most recent job ingestion timestamp, if any."""
    conn = database.connect()
    row = conn.execute(
        "SELECT MAX(ingested_at) AS ingested_at FROM jobs"
    ).fetchone()
    if row is None or row["ingested_at"] is None:
        return None
    return datetime.fromisoformat(row["ingested_at"])
