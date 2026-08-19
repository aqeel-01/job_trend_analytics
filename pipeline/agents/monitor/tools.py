"""Monitor Agent tools — callable checks for database, pipeline, and API health."""

import logging
from datetime import datetime, timezone

import httpx

from pipeline.storage.database import Database
from pipeline.storage.repositories import (
    JobRepository,
    JobSkillRepository,
    PipelineRunRepository,
)

logger = logging.getLogger(__name__)


def check_database_health(database: Database) -> dict:
    """Verify the database is reachable, initialized, and has required tables.

    Returns a dict with keys:
        healthy (bool), schema_version (int|None), tables (list[str]),
        has_required_tables (bool), detail (str).
    """
    try:
        version = database.schema_version()
        tables = sorted(database.table_names())
        has_required = database.has_required_tables()
        healthy = version is not None and has_required
        detail = (
            f"schema_v{version}, {len(tables)} tables, "
            f"required={'ok' if has_required else 'missing'}"
        )
        return {
            "healthy": healthy,
            "schema_version": version,
            "tables": tables,
            "has_required_tables": has_required,
            "detail": detail,
        }
    except Exception as exc:
        logger.exception("Database health check failed")
        return {
            "healthy": False,
            "schema_version": None,
            "tables": [],
            "has_required_tables": False,
            "detail": f"error: {exc}",
        }


def check_pipeline_status(
    database: Database,
    freshness_threshold_hours: float = 168.0,
) -> dict:
    """Check for new data, pipeline freshness, and ingestion failures.

    Returns a dict with keys:
        fresh (bool), new_data_exists (bool), ingestion_failure (bool),
        last_run_at (str|None), job_count (int), skill_link_count (int),
        detail (str).
    """
    try:
        job_repo = JobRepository(database)
        job_skill_repo = JobSkillRepository(database)
        pipeline_repo = PipelineRunRepository(database)

        job_count = job_repo.count_jobs()
        skill_link_count = job_skill_repo.count_links()
        runs = pipeline_repo.list_runs(limit=1)

        last_run = runs[0] if runs else None
        last_run_at: str | None = None
        fresh = False
        new_data = False
        failure = False

        if last_run is not None:
            last_run_at = last_run.started_at.isoformat() if last_run.started_at else None
            if last_run.started_at is not None:
                age_hours = (
                    datetime.now(timezone.utc) - last_run.started_at.replace(tzinfo=timezone.utc)
                ).total_seconds() / 3600
                fresh = age_hours < freshness_threshold_hours
            new_data = last_run.records_inserted > 0
            failure = last_run.status != "completed" or last_run.records_failed > 0

        detail_parts = [
            f"jobs={job_count}",
            f"skill_links={skill_link_count}",
            f"last_run={'none' if last_run_at is None else last_run_at}",
            f"fresh={fresh}",
            f"failure={failure}",
        ]
        return {
            "fresh": fresh,
            "new_data_exists": new_data,
            "ingestion_failure": failure,
            "last_run_at": last_run_at,
            "job_count": job_count,
            "skill_link_count": skill_link_count,
            "detail": ", ".join(detail_parts),
        }
    except Exception as exc:
        logger.exception("Pipeline status check failed")
        return {
            "fresh": False,
            "new_data_exists": False,
            "ingestion_failure": True,
            "last_run_at": None,
            "job_count": 0,
            "skill_link_count": 0,
            "detail": f"error: {exc}",
        }


def check_fastapi_health(
    base_url: str = "http://127.0.0.1:8000",
    timeout: float = 5.0,
) -> dict:
    """Probe the /health endpoint of the FastAPI model-serving layer.

    Returns a dict with keys:
        healthy (bool), status_code (int|None), body (dict|None), detail (str).
    """
    try:
        resp = httpx.get(f"{base_url}/health", timeout=timeout)
        body = resp.json() if resp.status_code == 200 else None
        healthy = resp.status_code == 200 and (body or {}).get("status") == "ok"
        return {
            "healthy": healthy,
            "status_code": resp.status_code,
            "body": body,
            "detail": f"status={resp.status_code} body={body}",
        }
    except httpx.ConnectError:
        return {
            "healthy": False,
            "status_code": None,
            "body": None,
            "detail": "connection refused — API not running",
        }
    except Exception as exc:
        logger.exception("FastAPI health check failed")
        return {
            "healthy": False,
            "status_code": None,
            "body": None,
            "detail": f"error: {exc}",
        }
