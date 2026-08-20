"""High-level metric recording helpers for V1 monitoring.

All recorders are best-effort: metric failures never break the pipeline.
"""

from __future__ import annotations

import logging
from typing import Any

from pipeline.monitoring.metrics import MetricName
from pipeline.monitoring.store import MetricsStore, get_metrics_store

logger = logging.getLogger(__name__)


def _safe_record(
    name: MetricName,
    *,
    value: float | int | None = None,
    unit: str | None = None,
    success: bool | None = None,
    labels: dict[str, Any] | None = None,
    detail: str | None = None,
    store: MetricsStore | None = None,
) -> None:
    try:
        metrics = store or get_metrics_store()
        metrics.record_metric(
            name,
            value=value,
            unit=unit,
            success=success,
            labels=labels,
            detail=detail,
        )
    except Exception as exc:
        logger.warning("Failed to record metric %s: %s", name.value, exc)


def record_api_failure(
    *,
    source: str = "arbeitnow",
    page: int | None = None,
    detail: str | None = None,
    store: MetricsStore | None = None,
) -> None:
    labels: dict[str, Any] = {"source": source}
    if page is not None:
        labels["page"] = page
    _safe_record(
        MetricName.API_FAILURES,
        value=1,
        success=False,
        labels=labels,
        detail=detail,
        store=store,
    )


def record_ingestion_run(
    *,
    latency_seconds: float,
    jobs_collected: int,
    jobs_inserted: int,
    jobs_duplicates: int,
    jobs_failed: int = 0,
    status: str = "completed",
    store: MetricsStore | None = None,
) -> None:
    labels = {
        "status": status,
        "inserted": jobs_inserted,
        "duplicates": jobs_duplicates,
        "failed": jobs_failed,
    }
    _safe_record(
        MetricName.INGESTION_LATENCY,
        value=round(latency_seconds, 4),
        unit="seconds",
        success=status in {"completed", "completed_with_errors"},
        labels=labels,
        store=store,
    )
    _safe_record(
        MetricName.JOBS_COLLECTED,
        value=jobs_collected,
        unit="jobs",
        success=True,
        labels=labels,
        store=store,
    )
    if jobs_collected > 0:
        duplicate_pct = (jobs_duplicates / jobs_collected) * 100.0
    else:
        duplicate_pct = 0.0
    _safe_record(
        MetricName.DUPLICATE_PERCENTAGE,
        value=round(duplicate_pct, 2),
        unit="percent",
        success=True,
        labels=labels,
        store=store,
    )


def record_preprocessing_failure(
    *,
    detail: str | None = None,
    store: MetricsStore | None = None,
) -> None:
    _safe_record(
        MetricName.PREPROCESSING_FAILURES,
        value=1,
        success=False,
        detail=detail,
        store=store,
    )


def record_model_execution_time(
    *,
    duration_seconds: float,
    success: bool = True,
    model_version: str | None = None,
    detail: str | None = None,
    store: MetricsStore | None = None,
) -> None:
    labels: dict[str, Any] = {}
    if model_version is not None:
        labels["model_version"] = model_version
    _safe_record(
        MetricName.MODEL_EXECUTION_TIME,
        value=round(duration_seconds, 4),
        unit="seconds",
        success=success,
        labels=labels,
        detail=detail,
        store=store,
    )


def record_agent_failure(
    *,
    agent: str,
    detail: str | None = None,
    store: MetricsStore | None = None,
) -> None:
    _safe_record(
        MetricName.AGENT_EXECUTION_FAILURES,
        value=1,
        success=False,
        labels={"agent": agent},
        detail=detail,
        store=store,
    )


def record_fastapi_health(
    *,
    healthy: bool,
    detail: str | None = None,
    status_code: int | None = None,
    store: MetricsStore | None = None,
) -> None:
    labels: dict[str, Any] = {}
    if status_code is not None:
        labels["status_code"] = status_code
    _safe_record(
        MetricName.FASTAPI_HEALTH,
        value=1 if healthy else 0,
        success=healthy,
        labels=labels,
        detail=detail,
        store=store,
    )


def record_report_generation(
    *,
    success: bool,
    detail: str | None = None,
    fallback: bool = False,
    store: MetricsStore | None = None,
) -> None:
    _safe_record(
        MetricName.REPORT_GENERATION_SUCCESS,
        value=1 if success else 0,
        success=success,
        labels={"fallback": fallback},
        detail=detail,
        store=store,
    )
