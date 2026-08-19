"""Tests for the Monitor Agent LangGraph workflow and state transitions."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from pipeline.agents.monitor.graph import (
    MonitorStateDict,
    build_monitor_graph,
    evaluate_node,
    run_monitor,
)
from pipeline.storage.database import Database


@pytest.fixture
def tmp_database(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def _insert_run(db, *, hours_ago=1, status="completed", inserted=10, failed=0):
    conn = db.connect()
    started = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    completed = started + timedelta(seconds=30)
    conn.execute(
        """INSERT INTO pipeline_runs
           (started_at, completed_at, status, records_fetched, records_inserted, records_failed)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (started.isoformat(), completed.isoformat(), status, inserted, inserted, failed),
    )
    conn.commit()


# -- Evaluate node unit tests ------------------------------------------------


class TestEvaluateNode:
    def test_healthy_with_new_data_triggers_analysis(self):
        state: MonitorStateDict = {
            "db_healthy": True,
            "pipeline_fresh": True,
            "ingestion_failure": False,
            "new_data_exists": True,
        }
        update = evaluate_node(state)
        assert update["status"] == "analysis_triggered"
        assert update["should_trigger_analysis"] is True

    def test_healthy_no_new_data(self):
        state: MonitorStateDict = {
            "db_healthy": True,
            "pipeline_fresh": True,
            "ingestion_failure": False,
            "new_data_exists": False,
        }
        update = evaluate_node(state)
        assert update["status"] == "healthy"
        assert update["should_trigger_analysis"] is False

    def test_db_unhealthy_results_in_error(self):
        state: MonitorStateDict = {
            "db_healthy": False,
            "pipeline_fresh": True,
            "ingestion_failure": False,
            "new_data_exists": True,
        }
        update = evaluate_node(state)
        assert update["status"] == "error"
        assert update["should_trigger_analysis"] is False

    def test_failure_detected(self):
        state: MonitorStateDict = {
            "db_healthy": True,
            "pipeline_fresh": True,
            "ingestion_failure": True,
            "new_data_exists": True,
        }
        update = evaluate_node(state)
        assert update["status"] == "failure_detected"

    def test_stale_pipeline(self):
        state: MonitorStateDict = {
            "db_healthy": True,
            "pipeline_fresh": False,
            "ingestion_failure": False,
            "new_data_exists": False,
        }
        update = evaluate_node(state)
        assert update["status"] == "stale"
        assert update["should_trigger_analysis"] is False


# -- Full workflow integration ------------------------------------------------


class TestRunMonitor:
    @patch("pipeline.agents.monitor.tools.check_fastapi_health")
    def test_healthy_workflow(self, mock_api, tmp_database):
        mock_api.return_value = {"healthy": True, "status_code": 200, "body": {}, "detail": "ok"}
        _insert_run(tmp_database, hours_ago=2)

        result = run_monitor(tmp_database, freshness_threshold_hours=24)

        assert result["db_healthy"] is True
        assert result["pipeline_fresh"] is True
        assert result["api_healthy"] is True
        assert result["status"] == "analysis_triggered"
        assert result["should_trigger_analysis"] is True
        assert len(result["tool_results"]) == 3

    @patch("pipeline.agents.monitor.tools.check_fastapi_health")
    def test_stale_workflow(self, mock_api, tmp_database):
        mock_api.return_value = {"healthy": True, "status_code": 200, "body": {}, "detail": "ok"}
        _insert_run(tmp_database, hours_ago=200)

        result = run_monitor(tmp_database, freshness_threshold_hours=168)
        assert result["status"] == "stale"
        assert result["should_trigger_analysis"] is False

    @patch("pipeline.agents.monitor.tools.check_fastapi_health")
    def test_failure_workflow(self, mock_api, tmp_database):
        mock_api.return_value = {"healthy": True, "status_code": 200, "body": {}, "detail": "ok"}
        _insert_run(tmp_database, status="failed", failed=5)

        result = run_monitor(tmp_database)
        assert result["status"] == "failure_detected"
        assert result["ingestion_failure"] is True

    def test_unhealthy_db_skips_pipeline_and_api(self):
        """When DB is unhealthy, the workflow should skip pipeline/API checks."""
        bad_db = MagicMock(spec=Database)
        bad_db.schema_version.side_effect = Exception("boom")
        bad_db.table_names.side_effect = Exception("boom")
        bad_db.has_required_tables.side_effect = Exception("boom")

        result = run_monitor(bad_db)
        assert result["status"] == "error"
        assert result["db_healthy"] is False
        assert result["pipeline_fresh"] is None
        assert result["api_healthy"] is None

    @patch("pipeline.agents.monitor.tools.check_fastapi_health")
    def test_no_runs_empty_db(self, mock_api, tmp_database):
        mock_api.return_value = {"healthy": False, "status_code": None, "body": None, "detail": "down"}
        result = run_monitor(tmp_database)
        assert result["db_healthy"] is True
        assert result["pipeline_fresh"] is False
        assert result["status"] == "stale"


class TestGraphStructure:
    def test_graph_compiles(self, tmp_database):
        graph = build_monitor_graph(tmp_database)
        compiled = graph.compile()
        assert compiled is not None

    def test_graph_has_expected_nodes(self, tmp_database):
        graph = build_monitor_graph(tmp_database)
        node_names = set(graph.nodes.keys())
        assert "check_db" in node_names
        assert "check_pipeline" in node_names
        assert "check_api" in node_names
        assert "evaluate" in node_names
