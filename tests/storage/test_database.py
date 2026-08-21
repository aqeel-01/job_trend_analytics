"""Tests for database initialization and schema."""

from pipeline.storage.database import Database
from pipeline.storage.schema import REQUIRED_TABLES, SCHEMA_VERSION


def test_database_initialization(database) -> None:
    assert database.schema_version() == SCHEMA_VERSION
    assert database.has_required_tables()
    assert set(REQUIRED_TABLES).issubset(database.table_names())


def test_initialize_is_idempotent(database) -> None:
    database.initialize()
    database.initialize()
    assert database.schema_version() == SCHEMA_VERSION
    assert database.has_required_tables()


def test_migration_adds_pipeline_runs_created_at(tmp_path) -> None:
    """Early V1 DBs missing pipeline_runs.created_at are repaired by schema v2."""
    import sqlite3

    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT INTO schema_migrations (version) VALUES (1);
        CREATE TABLE pipeline_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL,
            records_fetched INTEGER NOT NULL DEFAULT 0,
            records_inserted INTEGER NOT NULL DEFAULT 0,
            records_failed INTEGER NOT NULL DEFAULT 0,
            error_message TEXT
        );
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_job_id TEXT NOT NULL,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            description TEXT NOT NULL,
            url TEXT NOT NULL,
            published_at TEXT,
            remote INTEGER,
            source TEXT NOT NULL,
            ingested_at TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_name TEXT NOT NULL,
            category TEXT,
            canonical_name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE job_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            skill_id INTEGER NOT NULL,
            confidence REAL,
            extraction_method TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE model_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_version TEXT NOT NULL,
            trained_at TEXT NOT NULL,
            training_dataset_size INTEGER,
            model_parameters TEXT,
            evaluation_metrics TEXT,
            status TEXT NOT NULL DEFAULT 'completed',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE agent_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL,
            workflow_name TEXT,
            tool_calls_succeeded INTEGER NOT NULL DEFAULT 0,
            tool_calls_failed INTEGER NOT NULL DEFAULT 0,
            output_path TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    conn.commit()
    conn.close()

    database = Database(db_path)
    database.initialize()

    assert database.schema_version() == 2
    cols = {
        row["name"]
        for row in database.connect().execute("PRAGMA table_info(pipeline_runs)").fetchall()
    }
    assert "created_at" in cols
    database.close()
