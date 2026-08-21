"""Tests for Monitor Agent tool functions."""

import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from pipeline.agents.monitor.tools import (
    check_database_health,
    check_fastapi_health,
    check_pipeline_status,
)
from pipeline.storage.database import Database


@pytest.fixture
def tmp_database(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


# -- check_database_health ---------------------------------------------------


class TestCheckDatabaseHealth:
    def test_healthy_database(self, tmp_database):
        result = check_database_health(tmp_database)
        assert result["healthy"] is True
        assert result["schema_version"] is not None
        assert result["has_required_tables"] is True
        assert "tables" in result

    def test_uninitialised_database(self, tmp_path):
        db = Database(tmp_path / "empty.db")
        db.connect()  # creates file but no tables
        result = check_database_health(db)
        assert result["healthy"] is False

    def test_broken_connection(self):
        db = MagicMock(spec=Database)
        db.schema_version.side_effect = Exception("disk I/O error")
        result = check_database_health(db)
        assert result["healthy"] is False
        assert "error" in result["detail"]


# -- check_pipeline_status ---------------------------------------------------


class TestCheckPipelineStatus:
    def _insert_run(self, db, *, hours_ago=1, status="completed", inserted=10, failed=0):
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

    def test_fresh_successful_run(self, tmp_database):
        self._insert_run(tmp_database, hours_ago=2)
        result = check_pipeline_status(tmp_database, freshness_threshold_hours=24)
        assert result["fresh"] is True
        assert result["new_data_exists"] is True
        assert result["ingestion_failure"] is False

    def test_stale_data(self, tmp_database):
        self._insert_run(tmp_database, hours_ago=200)
        result = check_pipeline_status(tmp_database, freshness_threshold_hours=168)
        assert result["fresh"] is False

    def test_ingestion_failure_detected(self, tmp_database):
        self._insert_run(tmp_database, status="failed", failed=5)
        result = check_pipeline_status(tmp_database)
        assert result["ingestion_failure"] is True

    def test_no_runs(self, tmp_database):
        result = check_pipeline_status(tmp_database)
        assert result["fresh"] is False
        assert result["new_data_exists"] is False
        assert result["job_count"] == 0

    def test_run_with_zero_inserts(self, tmp_database):
        self._insert_run(tmp_database, inserted=0)
        result = check_pipeline_status(tmp_database)
        assert result["new_data_exists"] is False

    def test_check_error_does_not_look_like_ingestion_failure(self):
        from unittest.mock import MagicMock

        bad_db = MagicMock()
        bad_db.connect.side_effect = Exception("disk I/O error")
        # JobRepository etc. will fail when constructing/using
        from pipeline.storage.repositories import JobRepository

        with patch(
            "pipeline.agents.monitor.tools.JobRepository",
            side_effect=Exception("boom"),
        ):
            result = check_pipeline_status(bad_db)
        assert result["check_error"] is True
        assert result["ingestion_failure"] is False


# -- check_fastapi_health ----------------------------------------------------


class TestCheckFastapiHealth:
    def test_healthy_api(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok", "version": "0.1.0"}
        with patch("pipeline.agents.monitor.tools.httpx.get", return_value=mock_resp):
            result = check_fastapi_health()
        assert result["healthy"] is True
        assert result["status_code"] == 200

    def test_api_down(self):
        import httpx
        with patch("pipeline.agents.monitor.tools.httpx.get", side_effect=httpx.ConnectError("")):
            result = check_fastapi_health()
        assert result["healthy"] is False
        assert "connection refused" in result["detail"]

    def test_api_error_status(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = None
        with patch("pipeline.agents.monitor.tools.httpx.get", return_value=mock_resp):
            result = check_fastapi_health()
        assert result["healthy"] is False
