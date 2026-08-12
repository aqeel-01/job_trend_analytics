"""SQLite persistence for ingested job postings."""

import sqlite3
from datetime import datetime
from pathlib import Path

from pipeline.ingest.models import IngestionResult, JobPosting


class JobStorage:
    """Persist normalized jobs and ingestion run metadata to SQLite."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._connection: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """Open (or return) the database connection."""
        if self._connection is None:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(self.database_path)
            self._connection.row_factory = sqlite3.Row
        return self._connection

    def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def init_schema(self) -> None:
        """Create ingestion-related tables if they do not exist."""
        conn = self.connect()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
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

            CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_source_job
                ON jobs (source, source_job_id);

            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL,
                records_fetched INTEGER NOT NULL DEFAULT 0,
                records_inserted INTEGER NOT NULL DEFAULT 0,
                records_failed INTEGER NOT NULL DEFAULT 0,
                error_message TEXT
            );
            """
        )
        conn.commit()

    def insert_job(self, job: JobPosting) -> bool:
        """Insert a job if it is not a duplicate. Returns True when inserted."""
        conn = self.connect()
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO jobs (
                source_job_id, title, company, location, description,
                url, published_at, remote, source, ingested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.source_job_id,
                job.title,
                job.company,
                job.location,
                job.description,
                job.url,
                job.published_at.isoformat() if job.published_at else None,
                1 if job.remote is True else (0 if job.remote is False else None),
                job.source,
                job.ingested_at.isoformat(),
            ),
        )
        conn.commit()
        return cursor.rowcount > 0

    def count_jobs(self, source: str | None = None) -> int:
        """Return total stored jobs, optionally filtered by source."""
        conn = self.connect()
        if source is None:
            row = conn.execute("SELECT COUNT(*) AS count FROM jobs").fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM jobs WHERE source = ?",
                (source,),
            ).fetchone()
        return int(row["count"])

    def record_pipeline_run(
        self,
        started_at: datetime,
        completed_at: datetime,
        result: IngestionResult,
    ) -> int:
        """Persist pipeline run summary and return the run ID."""
        conn = self.connect()
        cursor = conn.execute(
            """
            INSERT INTO pipeline_runs (
                started_at, completed_at, status,
                records_fetched, records_inserted, records_failed, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                started_at.isoformat(),
                completed_at.isoformat(),
                result.status,
                result.records_fetched,
                result.records_inserted,
                result.records_failed,
                result.error_message,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
