"""Tests for V1 monitoring metrics store and recording."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from pipeline.monitoring.metrics import MetricEvent, MetricName
from pipeline.monitoring.recorder import (
    record_agent_failure,
    record_api_failure,
    record_fastapi_health,
    record_ingestion_run,
    record_model_execution_time,
    record_preprocessing_failure,
    record_report_generation,
)
from pipeline.monitoring.store import MetricsStore, get_metrics_store, reset_metrics_store


class TestMetricsStore:
    def test_record_and_read(self, tmp_path):
        store = MetricsStore(tmp_path / "m.jsonl")
        store.record_metric(MetricName.API_FAILURES, value=1, success=False, detail="timeout")

        events = store.read_all()
        assert len(events) == 1
        assert events[0].name == MetricName.API_FAILURES.value
        assert events[0].success is False
        assert events[0].detail == "timeout"

    def test_filter_by_name_and_success(self, tmp_path):
        store = MetricsStore(tmp_path / "m.jsonl")
        store.record_metric(MetricName.FASTAPI_HEALTH, success=True)
        store.record_metric(MetricName.FASTAPI_HEALTH, success=False)
        store.record_metric(MetricName.API_FAILURES, success=False)

        healthy = store.filter(MetricName.FASTAPI_HEALTH, success=True)
        assert len(healthy) == 1
        assert store.count(MetricName.API_FAILURES) == 1

    def test_malformed_line_skipped(self, tmp_path):
        path = tmp_path / "m.jsonl"
        path.write_text('{"name":"api_failures","recorded_at":"t"}\nNOT_JSON\n', encoding="utf-8")
        store = MetricsStore(path)
        events = store.read_all()
        assert len(events) == 1

    def test_summary_aggregates_srs_metrics(self, tmp_path):
        store = MetricsStore(tmp_path / "m.jsonl")
        record_api_failure(detail="boom", store=store)
        record_ingestion_run(
            latency_seconds=1.5,
            jobs_collected=100,
            jobs_inserted=80,
            jobs_duplicates=20,
            store=store,
        )
        record_preprocessing_failure(detail="bad html", store=store)
        record_model_execution_time(duration_seconds=0.25, store=store)
        record_agent_failure(agent="analyst", detail="api down", store=store)
        record_fastapi_health(healthy=True, detail="ok", store=store)
        record_report_generation(success=True, store=store)

        summary = store.summary()
        assert summary["api_failures"] == 1
        assert summary["ingestion_latency_seconds_avg"] == 1.5
        assert summary["jobs_collected_total"] == 100
        assert summary["duplicate_percentage_latest"] == 20.0
        assert summary["preprocessing_failures"] == 1
        assert summary["model_execution_time_seconds_avg"] == 0.25
        assert summary["agent_execution_failures"] == 1
        assert summary["fastapi_health_latest"]["success"] is True
        assert summary["report_generation_success_count"] == 1
        assert summary["report_generation_failure_count"] == 0

    def test_clear(self, tmp_path):
        store = MetricsStore(tmp_path / "m.jsonl")
        store.record_metric(MetricName.API_FAILURES, value=1)
        store.clear()
        assert store.read_all() == []


class TestRecorders:
    def test_duplicate_percentage_zero_when_no_jobs(self, metrics_store):
        record_ingestion_run(
            latency_seconds=0.1,
            jobs_collected=0,
            jobs_inserted=0,
            jobs_duplicates=0,
            store=metrics_store,
        )
        events = metrics_store.filter(MetricName.DUPLICATE_PERCENTAGE)
        assert events[-1].value == 0.0

    def test_recorder_swallows_store_errors(self):
        bad_store = MagicMock()
        bad_store.record_metric.side_effect = OSError("disk full")
        record_api_failure(detail="x", store=bad_store)  # must not raise

    def test_report_failure_recording(self, metrics_store):
        record_report_generation(success=False, detail="invalid input", store=metrics_store)
        events = metrics_store.filter(MetricName.REPORT_GENERATION_SUCCESS, success=False)
        assert len(events) == 1


class TestIngestionMetricsIntegration:
    def test_ingestion_records_latency_jobs_and_duplicates(
        self, job_repository, pipeline_run_repository, database, metrics_store
    ):
        from tests.ingest.test_service import MockJobBoardClient, _build_service, _load_fixture

        page_one = _load_fixture("arbeitnow_page.json")
        client = MockJobBoardClient({1: page_one})
        service = _build_service(client, job_repository, pipeline_run_repository, database)

        service.run()
        service.run()  # second run = all duplicates

        assert metrics_store.count(MetricName.INGESTION_LATENCY) == 2
        assert metrics_store.count(MetricName.JOBS_COLLECTED) == 2
        dup_events = metrics_store.filter(MetricName.DUPLICATE_PERCENTAGE)
        assert dup_events[-1].value == 100.0

    def test_api_failure_metric_on_client_exhaustion(self, metrics_store, monkeypatch):
        from pipeline.ingest.client import ArbeitnowClient
        from pipeline.ingest.exceptions import APIRequestError

        client = ArbeitnowClient(base_url="https://example.test/api", max_retries=1)

        def _fail(_url: str):
            raise httpx.ConnectError("down")

        monkeypatch.setattr(client, "_request", _fail)

        with pytest.raises(APIRequestError):
            client.fetch_page(1)

        assert metrics_store.count(MetricName.API_FAILURES) == 1


class TestPreprocessingFailureMetric:
    def test_preprocess_records_unexpected_failure(self, metrics_store, monkeypatch):
        from pipeline.preprocess import text as text_mod

        def _boom(_text: str) -> str:
            raise RuntimeError("strip failed")

        monkeypatch.setattr(text_mod, "_strip_html", _boom)

        with pytest.raises(RuntimeError):
            text_mod.preprocess_description("<p>x</p>")

        assert metrics_store.count(MetricName.PREPROCESSING_FAILURES) == 1


class TestModelExecutionMetric:
    def test_trend_service_records_execution_time(self, database, metrics_store):
        from pipeline.storage.repositories import ModelRunRepository
        from pipeline.trend.model import TrendModel
        from pipeline.trend.service import TrendModelService

        service = TrendModelService(TrendModel(), ModelRunRepository(database))
        weekly = [
            {"Python": 10},
            {"Python": 12},
            {"Python": 20},
        ]
        service.run_and_record(weekly)

        events = metrics_store.filter(MetricName.MODEL_EXECUTION_TIME)
        assert len(events) == 1
        assert events[0].success is True
        assert events[0].value is not None
        assert events[0].value >= 0


class TestFastapiHealthMetric:
    def test_health_check_records_failure(self, metrics_store):
        with patch("pipeline.agents.monitor.tools.httpx.get", side_effect=httpx.ConnectError("")):
            from pipeline.agents.monitor.tools import check_fastapi_health

            result = check_fastapi_health()
        assert result["healthy"] is False
        events = metrics_store.filter(MetricName.FASTAPI_HEALTH)
        assert events[-1].success is False

    def test_health_endpoint_records_success(self, metrics_store):
        from fastapi.testclient import TestClient

        from pipeline.api.app import create_app

        app = create_app()
        with TestClient(app) as test_client:
            response = test_client.get("/health")
        assert response.status_code == 200
        events = metrics_store.filter(MetricName.FASTAPI_HEALTH, success=True)
        assert len(events) >= 1


class TestAgentAndReportMetrics:
    def test_report_writer_records_success(self, metrics_store):
        from tests.agents.report_writer.conftest import VALID_ANALYST_REPORT

        with patch(
            "pipeline.agents.report_writer.graph.generate_with_ollama",
            return_value={
                "success": True,
                "text": "## Executive Summary\nOk\n",
                "model": "llama3",
                "detail": "ok",
            },
        ):
            from pipeline.agents.report_writer.graph import run_report_writer

            result = run_report_writer(VALID_ANALYST_REPORT)

        assert result["status"] == "completed"
        assert metrics_store.count(MetricName.REPORT_GENERATION_SUCCESS) == 1
        assert metrics_store.filter(MetricName.REPORT_GENERATION_SUCCESS)[0].success is True

    def test_report_writer_records_failure_on_invalid_input(self, metrics_store):
        from pipeline.agents.report_writer.graph import run_report_writer

        result = run_report_writer(None)
        assert result["status"] == "invalid_input"
        failed = metrics_store.filter(MetricName.REPORT_GENERATION_SUCCESS, success=False)
        assert len(failed) == 1

    def test_orchestrator_records_agent_failure_on_unhealthy_db(self, tmp_path, metrics_store):
        bad_db = MagicMock()
        bad_db.schema_version.side_effect = Exception("boom")
        bad_db.table_names.side_effect = Exception("boom")
        bad_db.has_required_tables.side_effect = Exception("boom")
        bad_db.connect.return_value = MagicMock()
        bad_db.connect.return_value.execute.return_value = MagicMock(lastrowid=99)

        from pipeline.agents.orchestrator.graph import run_orchestrator

        result = run_orchestrator(
            database=bad_db,
            report_output_dir=str(tmp_path / "reports"),
        )
        assert result["status"] == "monitor_error"
        failures = metrics_store.filter(MetricName.AGENT_EXECUTION_FAILURES)
        assert len(failures) == 1
        assert failures[0].labels.get("agent") == "monitor"


class TestMetricEvent:
    def test_round_trip(self):
        event = MetricEvent.create(
            MetricName.JOBS_COLLECTED,
            value=42,
            unit="jobs",
            success=True,
            labels={"status": "completed"},
        )
        restored = MetricEvent.from_dict(event.to_dict())
        assert restored.name == event.name
        assert restored.value == 42
        assert restored.labels["status"] == "completed"
