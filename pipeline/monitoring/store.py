"""JSONL-backed local metrics store for V1 monitoring."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

from pipeline.monitoring.metrics import MetricEvent, MetricName

logger = logging.getLogger(__name__)

_store: MetricsStore | None = None
_lock = threading.Lock()


class MetricsStore:
    """Append-only JSONL metrics store suitable for local V1 observability."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._write_lock = threading.Lock()

    def record(self, event: MetricEvent) -> MetricEvent:
        """Persist a metric event to the JSONL file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event.to_dict(), default=str)
        with self._write_lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        logger.debug("metric recorded: %s value=%s success=%s", event.name, event.value, event.success)
        return event

    def record_metric(
        self,
        name: str | MetricName,
        *,
        value: float | int | None = None,
        unit: str | None = None,
        success: bool | None = None,
        labels: dict[str, Any] | None = None,
        detail: str | None = None,
    ) -> MetricEvent:
        """Create and persist a metric event."""
        event = MetricEvent.create(
            name,
            value=value,
            unit=unit,
            success=success,
            labels=labels,
            detail=detail,
        )
        return self.record(event)

    def read_all(self) -> list[MetricEvent]:
        """Return all recorded events in order."""
        if not self.path.is_file():
            return []
        events: list[MetricEvent] = []
        with self.path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    events.append(MetricEvent.from_dict(json.loads(stripped)))
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    logger.warning(
                        "Skipping malformed metrics line %s in %s: %s",
                        line_number,
                        self.path,
                        exc,
                    )
        return events

    def filter(
        self,
        name: str | MetricName | None = None,
        *,
        success: bool | None = None,
    ) -> list[MetricEvent]:
        """Return events filtered by metric name and/or success flag."""
        target = name.value if isinstance(name, MetricName) else name
        events = self.read_all()
        if target is not None:
            events = [e for e in events if e.name == target]
        if success is not None:
            events = [e for e in events if e.success is success]
        return events

    def count(self, name: str | MetricName | None = None) -> int:
        return len(self.filter(name))

    def clear(self) -> None:
        """Delete the metrics file if it exists."""
        if self.path.is_file():
            self.path.unlink()

    def summary(self) -> dict[str, Any]:
        """Aggregate a compact summary of all tracked V1 metrics."""
        events = self.read_all()
        by_name: dict[str, list[MetricEvent]] = {}
        for event in events:
            by_name.setdefault(event.name, []).append(event)

        def _avg(values: list[float]) -> float | None:
            return sum(values) / len(values) if values else None

        def _latest(items: list[MetricEvent]) -> MetricEvent | None:
            return items[-1] if items else None

        api_failures = by_name.get(MetricName.API_FAILURES.value, [])
        latency = by_name.get(MetricName.INGESTION_LATENCY.value, [])
        jobs = by_name.get(MetricName.JOBS_COLLECTED.value, [])
        duplicates = by_name.get(MetricName.DUPLICATE_PERCENTAGE.value, [])
        preprocess = by_name.get(MetricName.PREPROCESSING_FAILURES.value, [])
        model_time = by_name.get(MetricName.MODEL_EXECUTION_TIME.value, [])
        agent_failures = by_name.get(MetricName.AGENT_EXECUTION_FAILURES.value, [])
        fastapi = by_name.get(MetricName.FASTAPI_HEALTH.value, [])
        reports = by_name.get(MetricName.REPORT_GENERATION_SUCCESS.value, [])

        latest_fastapi = _latest(fastapi)
        report_successes = sum(1 for e in reports if e.success)
        report_failures = sum(1 for e in reports if e.success is False)

        return {
            "total_events": len(events),
            "api_failures": len(api_failures),
            "ingestion_latency_seconds_avg": _avg(
                [float(e.value) for e in latency if e.value is not None]
            ),
            "jobs_collected_total": sum(
                int(e.value) for e in jobs if e.value is not None
            ),
            "duplicate_percentage_latest": (
                float(duplicates[-1].value)
                if duplicates and duplicates[-1].value is not None
                else None
            ),
            "preprocessing_failures": len(preprocess),
            "model_execution_time_seconds_avg": _avg(
                [float(e.value) for e in model_time if e.value is not None]
            ),
            "agent_execution_failures": len(agent_failures),
            "fastapi_health_latest": (
                {
                    "success": latest_fastapi.success,
                    "detail": latest_fastapi.detail,
                    "recorded_at": latest_fastapi.recorded_at,
                }
                if latest_fastapi is not None
                else None
            ),
            "report_generation_success_count": report_successes,
            "report_generation_failure_count": report_failures,
            "metrics_path": str(self.path),
        }


def get_metrics_store(path: Path | None = None) -> MetricsStore:
    """Return the process-wide metrics store (optionally rebinding the path)."""
    global _store
    with _lock:
        if path is not None:
            _store = MetricsStore(path)
            return _store
        if _store is None:
            from pipeline.config.settings import get_settings

            _store = MetricsStore(get_settings().metrics_path)
        return _store


def reset_metrics_store() -> None:
    """Clear the cached store singleton (used by tests)."""
    global _store
    with _lock:
        _store = None
