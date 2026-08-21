"""End-to-end tests for the V1 pipeline orchestrator.

All external dependencies (FastAPI, Ollama, live DB state) are mocked so the
full Monitor → Analyst → Report Writer chain can be validated deterministically.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from pipeline.agents.orchestrator.graph import (
    OrchestratorStateDict,
    build_orchestrator_graph,
    run_orchestrator,
)
from pipeline.storage.database import Database
from pipeline.storage.repositories import AgentRunRepository


@pytest.fixture
def tmp_database(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def _insert_fresh_run(db, hours_ago=2, inserted=10):
    conn = db.connect()
    started = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    completed = started + timedelta(seconds=30)
    conn.execute(
        """INSERT INTO pipeline_runs
           (started_at, completed_at, status, records_fetched, records_inserted, records_failed)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (started.isoformat(), completed.isoformat(), "completed", inserted, inserted, 0),
    )
    conn.commit()


MOCK_TRENDING_RESPONSE = {
    "model_version": "v1.0",
    "generated_at": "2026-08-19T12:00:00Z",
    "period_count": 4,
    "limit": 200,
    "total_skills": 3,
    "skills": [
        {
            "skill": "Python",
            "current_mentions": 80,
            "previous_mentions": 40,
            "change": 40,
            "change_percent": 100.0,
            "historical_mean": 35.0,
            "historical_std": 5.0,
            "z_score": 9.0,
            "trend": "rising",
            "direction": "up",
        },
        {
            "skill": "Java",
            "current_mentions": 30,
            "previous_mentions": 50,
            "change": -20,
            "change_percent": -40.0,
            "historical_mean": 45.0,
            "historical_std": 5.0,
            "z_score": -3.0,
            "trend": "falling",
            "direction": "down",
        },
        {
            "skill": "Go",
            "current_mentions": 20,
            "previous_mentions": 19,
            "change": 1,
            "change_percent": 5.26,
            "historical_mean": 19.0,
            "historical_std": 2.0,
            "z_score": 0.5,
            "trend": "stable",
            "direction": "flat",
        },
    ],
}

MOCK_MODEL_INFO = {"model_version": "v1.0", "method": "z_score"}

MOCK_LLM_RESPONSE = """\
## Executive Summary

Python surged by 100% while Java declined by 40%.

## Rising Skills

- **Python**: 40→80 mentions (+100.0%), z-score 9.00.

## Declining Skills

- **Java**: 50→30 mentions (-40.0%), z-score -3.00.

## Stable Skills

Go showed no significant change.

## Weak Signals

No weak signals this period.

## Methodology Note

Model v1.0, z-score method, 4 periods."""


def _mock_monitor_api_healthy(*args, **kwargs):
    return {"healthy": True, "status_code": 200, "body": {"status": "ok"}, "detail": "ok"}


def _mock_analyst_trending(*args, **kwargs):
    return {"success": True, "data": MOCK_TRENDING_RESPONSE, "detail": "ok"}


def _mock_analyst_model_info(*args, **kwargs):
    return {"success": True, "data": MOCK_MODEL_INFO, "detail": "ok"}


def _mock_ollama_success(*args, **kwargs):
    return {"success": True, "text": MOCK_LLM_RESPONSE, "model": "llama3", "detail": "ok"}


def _mock_ollama_failure(*args, **kwargs):
    return {"success": False, "text": "", "model": "llama3", "detail": "connection refused"}


# ---------------------------------------------------------------------------
# End-to-end: full pipeline completes successfully
# ---------------------------------------------------------------------------


class TestFullPipelineSuccess:
    @patch("pipeline.agents.report_writer.graph.generate_with_ollama", side_effect=_mock_ollama_success)
    @patch("pipeline.agents.analyst.graph.fetch_model_info", side_effect=_mock_analyst_model_info)
    @patch("pipeline.agents.analyst.graph.fetch_trending_skills", side_effect=_mock_analyst_trending)
    @patch("pipeline.agents.monitor.graph.check_fastapi_health", side_effect=_mock_monitor_api_healthy)
    def test_end_to_end_completed(self, m_api, m_trends, m_info, m_llm, tmp_database, tmp_path):
        _insert_fresh_run(tmp_database, hours_ago=2)

        result = run_orchestrator(
            database=tmp_database,
            freshness_threshold_hours=24,
            report_output_dir=str(tmp_path / "reports"),
        )

        assert result["status"] == "completed"
        assert result["agent_run_id"] is not None
        assert result["monitor_result"] is not None
        assert result["analyst_result"] is not None
        assert result["report_writer_result"] is not None
        assert result["error"] is None

    @patch("pipeline.agents.report_writer.graph.generate_with_ollama", side_effect=_mock_ollama_success)
    @patch("pipeline.agents.analyst.graph.fetch_model_info", side_effect=_mock_analyst_model_info)
    @patch("pipeline.agents.analyst.graph.fetch_trending_skills", side_effect=_mock_analyst_trending)
    @patch("pipeline.agents.monitor.graph.check_fastapi_health", side_effect=_mock_monitor_api_healthy)
    def test_agent_run_recorded_in_sqlite(self, m_api, m_trends, m_info, m_llm, tmp_database, tmp_path):
        _insert_fresh_run(tmp_database)
        result = run_orchestrator(
            database=tmp_database,
            freshness_threshold_hours=24,
            report_output_dir=str(tmp_path / "reports"),
        )

        repo = AgentRunRepository(tmp_database)
        run = repo.get_by_id(result["agent_run_id"])
        assert run is not None
        assert run.status == "completed"
        assert run.workflow_name == "v1_pipeline_orchestrator"
        assert run.tool_calls_succeeded > 0

    @patch("pipeline.agents.report_writer.graph.generate_with_ollama", side_effect=_mock_ollama_success)
    @patch("pipeline.agents.analyst.graph.fetch_model_info", side_effect=_mock_analyst_model_info)
    @patch("pipeline.agents.analyst.graph.fetch_trending_skills", side_effect=_mock_analyst_trending)
    @patch("pipeline.agents.monitor.graph.check_fastapi_health", side_effect=_mock_monitor_api_healthy)
    def test_report_file_written(self, m_api, m_trends, m_info, m_llm, tmp_database, tmp_path):
        _insert_fresh_run(tmp_database)
        result = run_orchestrator(
            database=tmp_database,
            freshness_threshold_hours=24,
            report_output_dir=str(tmp_path / "reports"),
        )

        assert result["output_path"] is not None
        from pathlib import Path
        report_file = Path(result["output_path"])
        assert report_file.exists()
        content = report_file.read_text(encoding="utf-8")
        assert "Python" in content

    @patch("pipeline.agents.report_writer.graph.generate_with_ollama", side_effect=_mock_ollama_success)
    @patch("pipeline.agents.analyst.graph.fetch_model_info", side_effect=_mock_analyst_model_info)
    @patch("pipeline.agents.analyst.graph.fetch_trending_skills", side_effect=_mock_analyst_trending)
    @patch("pipeline.agents.monitor.graph.check_fastapi_health", side_effect=_mock_monitor_api_healthy)
    def test_tool_calls_counted(self, m_api, m_trends, m_info, m_llm, tmp_database, tmp_path):
        _insert_fresh_run(tmp_database)
        result = run_orchestrator(
            database=tmp_database,
            freshness_threshold_hours=24,
            report_output_dir=str(tmp_path / "reports"),
        )
        assert result["tool_calls_succeeded"] >= 5  # monitor(3) + analyst(2) + rw(2)


# ---------------------------------------------------------------------------
# Monitor skips analysis when no trigger
# ---------------------------------------------------------------------------


class TestMonitorSkipsAnalysis:
    @patch("pipeline.agents.monitor.graph.check_fastapi_health", side_effect=_mock_monitor_api_healthy)
    def test_stale_data_skips_analyst(self, m_api, tmp_database, tmp_path):
        _insert_fresh_run(tmp_database, hours_ago=200)

        result = run_orchestrator(
            database=tmp_database,
            freshness_threshold_hours=168,
            report_output_dir=str(tmp_path / "reports"),
        )

        assert "skipped" in result["status"]
        assert result["analyst_result"] is None
        assert result["report_writer_result"] is None
        assert result["agent_run_id"] is not None

    def test_unhealthy_db_skips_all(self, tmp_path):
        from unittest.mock import MagicMock
        bad_db = MagicMock(spec=Database)
        bad_db.schema_version.side_effect = Exception("boom")
        bad_db.table_names.side_effect = Exception("boom")
        bad_db.has_required_tables.side_effect = Exception("boom")
        # AgentRunRepository.create needs a working connection
        bad_db.connect.return_value = MagicMock()
        bad_db.connect.return_value.execute.return_value = MagicMock(lastrowid=1)

        result = run_orchestrator(
            database=bad_db,
            report_output_dir=str(tmp_path / "reports"),
        )

        assert result["status"] == "monitor_error"
        assert result["analyst_result"] is None


# ---------------------------------------------------------------------------
# Failure propagation
# ---------------------------------------------------------------------------


class TestFailurePropagation:
    @patch("pipeline.agents.analyst.graph.fetch_trending_skills")
    @patch("pipeline.agents.monitor.graph.check_fastapi_health", side_effect=_mock_monitor_api_healthy)
    def test_analyst_failure_recorded(self, m_api, m_trends, tmp_database, tmp_path):
        _insert_fresh_run(tmp_database)
        m_trends.return_value = {"success": False, "data": None, "detail": "API down"}

        result = run_orchestrator(
            database=tmp_database,
            freshness_threshold_hours=24,
            report_output_dir=str(tmp_path / "reports"),
        )

        # analyst errors but report writer still runs with None report → invalid_input
        assert result["agent_run_id"] is not None
        repo = AgentRunRepository(tmp_database)
        run = repo.get_by_id(result["agent_run_id"])
        assert run is not None
        assert run.error_message is not None

    @patch("pipeline.agents.report_writer.graph.generate_with_ollama", side_effect=_mock_ollama_failure)
    @patch("pipeline.agents.analyst.graph.fetch_model_info", side_effect=_mock_analyst_model_info)
    @patch("pipeline.agents.analyst.graph.fetch_trending_skills", side_effect=_mock_analyst_trending)
    @patch("pipeline.agents.monitor.graph.check_fastapi_health", side_effect=_mock_monitor_api_healthy)
    def test_llm_failure_uses_fallback(self, m_api, m_trends, m_info, m_llm, tmp_database, tmp_path):
        _insert_fresh_run(tmp_database)
        result = run_orchestrator(
            database=tmp_database,
            freshness_threshold_hours=24,
            report_output_dir=str(tmp_path / "reports"),
        )

        assert result["status"] == "completed"
        rw = result["report_writer_result"]
        assert rw["report"]["llm_model_used"] == "fallback (no LLM)"


# ---------------------------------------------------------------------------
# Graph structure
# ---------------------------------------------------------------------------


class TestGraphStructure:
    def test_graph_compiles(self, tmp_database):
        graph = build_orchestrator_graph(tmp_database)
        compiled = graph.compile()
        assert compiled is not None

    def test_graph_has_expected_nodes(self, tmp_database):
        graph = build_orchestrator_graph(tmp_database)
        node_names = set(graph.nodes.keys())
        assert "monitor" in node_names
        assert "analyst" in node_names
        assert "report_writer" in node_names
        assert "record_run" in node_names
