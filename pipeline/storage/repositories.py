"""Repository layer for SQLite persistence."""

import json
from datetime import datetime

from pipeline.ingest.models import IngestionResult, JobPosting
from pipeline.storage.database import Database
from pipeline.storage.models import (
    JobInsertResult,
    StoredAgentRun,
    StoredJob,
    StoredJobSkill,
    StoredModelRun,
    StoredPipelineRun,
    StoredSkill,
)


def _datetime_to_str(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _str_to_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _bool_to_remote_int(value: bool | None) -> int | None:
    if value is None:
        return None
    return 1 if value else 0


def _remote_int_to_bool(value: int | None) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _job_from_row(row) -> StoredJob:
    return StoredJob(
        id=int(row["id"]),
        source_job_id=row["source_job_id"],
        title=row["title"],
        company=row["company"],
        location=row["location"],
        description=row["description"],
        url=row["url"],
        published_at=_str_to_datetime(row["published_at"]),
        remote=_remote_int_to_bool(row["remote"]),
        source=row["source"],
        ingested_at=_str_to_datetime(row["ingested_at"]),
        created_at=_str_to_datetime(row["created_at"]),
    )


class JobRepository:
    """CRUD operations for the jobs table."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def insert_job(self, job: JobPosting) -> JobInsertResult:
        """Insert a job when it is not a duplicate."""
        conn = self.database.connect()
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
                _datetime_to_str(job.published_at),
                _bool_to_remote_int(job.remote),
                job.source,
                _datetime_to_str(job.ingested_at),
            ),
        )
        conn.commit()

        if cursor.rowcount > 0:
            return JobInsertResult(inserted=True, job_id=int(cursor.lastrowid))

        existing = self.get_by_source_job_id(job.source, job.source_job_id)
        return JobInsertResult(
            inserted=False,
            job_id=existing.id if existing is not None else None,
        )

    def exists(self, source: str, source_job_id: str) -> bool:
        """Return True when a job already exists for the source identifier."""
        conn = self.database.connect()
        row = conn.execute(
            """
            SELECT 1 FROM jobs
            WHERE source = ? AND source_job_id = ?
            """,
            (source, source_job_id),
        ).fetchone()
        return row is not None

    def get_by_id(self, job_id: int) -> StoredJob | None:
        """Fetch a job by internal ID."""
        conn = self.database.connect()
        row = conn.execute(
            "SELECT * FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        return _job_from_row(row)

    def get_by_source_job_id(self, source: str, source_job_id: str) -> StoredJob | None:
        """Fetch a job by external source identifier."""
        conn = self.database.connect()
        row = conn.execute(
            """
            SELECT * FROM jobs
            WHERE source = ? AND source_job_id = ?
            """,
            (source, source_job_id),
        ).fetchone()
        if row is None:
            return None
        return _job_from_row(row)

    def list_jobs(
        self,
        limit: int = 100,
        offset: int = 0,
        source: str | None = None,
    ) -> list[StoredJob]:
        """List jobs with optional source filter."""
        conn = self.database.connect()
        if source is None:
            rows = conn.execute(
                """
                SELECT * FROM jobs
                ORDER BY ingested_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM jobs
                WHERE source = ?
                ORDER BY ingested_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (source, limit, offset),
            ).fetchall()
        return [_job_from_row(row) for row in rows]

    def count_jobs(self, source: str | None = None) -> int:
        """Return total job count, optionally filtered by source."""
        conn = self.database.connect()
        if source is None:
            row = conn.execute("SELECT COUNT(*) AS count FROM jobs").fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM jobs WHERE source = ?",
                (source,),
            ).fetchone()
        return int(row["count"])

    def delete_by_id(self, job_id: int) -> bool:
        """Delete a job by internal ID."""
        conn = self.database.connect()
        cursor = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        conn.commit()
        return cursor.rowcount > 0


class SkillRepository:
    """CRUD operations for the skills taxonomy table."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def create(
        self,
        skill_name: str,
        canonical_name: str,
        category: str | None = None,
    ) -> int:
        """Create a skill and return its ID."""
        conn = self.database.connect()
        cursor = conn.execute(
            """
            INSERT INTO skills (skill_name, category, canonical_name)
            VALUES (?, ?, ?)
            """,
            (skill_name, category, canonical_name),
        )
        conn.commit()
        return int(cursor.lastrowid)

    def get_by_id(self, skill_id: int) -> StoredSkill | None:
        """Fetch a skill by ID."""
        conn = self.database.connect()
        row = conn.execute(
            "SELECT * FROM skills WHERE id = ?",
            (skill_id,),
        ).fetchone()
        if row is None:
            return None
        return StoredSkill(
            id=int(row["id"]),
            skill_name=row["skill_name"],
            category=row["category"],
            canonical_name=row["canonical_name"],
            created_at=_str_to_datetime(row["created_at"]),
        )

    def get_by_canonical_name(self, canonical_name: str) -> StoredSkill | None:
        """Fetch a skill by canonical name."""
        conn = self.database.connect()
        row = conn.execute(
            "SELECT * FROM skills WHERE canonical_name = ?",
            (canonical_name,),
        ).fetchone()
        if row is None:
            return None
        return StoredSkill(
            id=int(row["id"]),
            skill_name=row["skill_name"],
            category=row["category"],
            canonical_name=row["canonical_name"],
            created_at=_str_to_datetime(row["created_at"]),
        )

    def list_skills(self, limit: int = 100, offset: int = 0) -> list[StoredSkill]:
        """List skills ordered by canonical name."""
        conn = self.database.connect()
        rows = conn.execute(
            """
            SELECT * FROM skills
            ORDER BY canonical_name ASC, id ASC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return [
            StoredSkill(
                id=int(row["id"]),
                skill_name=row["skill_name"],
                category=row["category"],
                canonical_name=row["canonical_name"],
                created_at=_str_to_datetime(row["created_at"]),
            )
            for row in rows
        ]

    def count_skills(self) -> int:
        """Return total skill count."""
        conn = self.database.connect()
        row = conn.execute("SELECT COUNT(*) AS count FROM skills").fetchone()
        return int(row["count"])


class JobSkillRepository:
    """CRUD operations for job-to-skill associations."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def link(
        self,
        job_id: int,
        skill_id: int,
        confidence: float | None = None,
        extraction_method: str | None = None,
    ) -> int:
        """Link a skill to a job, ignoring duplicates."""
        conn = self.database.connect()
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO job_skills (
                job_id, skill_id, confidence, extraction_method
            ) VALUES (?, ?, ?, ?)
            """,
            (job_id, skill_id, confidence, extraction_method),
        )
        conn.commit()
        if cursor.rowcount > 0:
            return int(cursor.lastrowid)

        row = conn.execute(
            """
            SELECT id FROM job_skills
            WHERE job_id = ? AND skill_id = ?
            """,
            (job_id, skill_id),
        ).fetchone()
        return int(row["id"])

    def get_for_job(self, job_id: int) -> list[StoredJobSkill]:
        """Return all skill links for a job."""
        conn = self.database.connect()
        rows = conn.execute(
            """
            SELECT * FROM job_skills
            WHERE job_id = ?
            ORDER BY id ASC
            """,
            (job_id,),
        ).fetchall()
        return [
            StoredJobSkill(
                id=int(row["id"]),
                job_id=int(row["job_id"]),
                skill_id=int(row["skill_id"]),
                confidence=row["confidence"],
                extraction_method=row["extraction_method"],
                created_at=_str_to_datetime(row["created_at"]),
            )
            for row in rows
        ]

    def count_for_job(self, job_id: int) -> int:
        """Return number of skills linked to a job."""
        conn = self.database.connect()
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM job_skills WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        return int(row["count"])


class PipelineRunRepository:
    """CRUD operations for pipeline run metadata."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def create(
        self,
        started_at: datetime,
        completed_at: datetime | None,
        status: str,
        records_fetched: int = 0,
        records_inserted: int = 0,
        records_failed: int = 0,
        error_message: str | None = None,
    ) -> int:
        """Record a pipeline run and return its ID."""
        conn = self.database.connect()
        cursor = conn.execute(
            """
            INSERT INTO pipeline_runs (
                started_at, completed_at, status,
                records_fetched, records_inserted, records_failed, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _datetime_to_str(started_at),
                _datetime_to_str(completed_at),
                status,
                records_fetched,
                records_inserted,
                records_failed,
                error_message,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)

    def create_from_ingestion_result(
        self,
        started_at: datetime,
        completed_at: datetime,
        result: IngestionResult,
    ) -> int:
        """Record an ingestion run from an IngestionResult."""
        return self.create(
            started_at=started_at,
            completed_at=completed_at,
            status=result.status,
            records_fetched=result.records_fetched,
            records_inserted=result.records_inserted,
            records_failed=result.records_failed,
            error_message=result.error_message,
        )

    def get_by_id(self, run_id: int) -> StoredPipelineRun | None:
        """Fetch a pipeline run by ID."""
        conn = self.database.connect()
        row = conn.execute(
            "SELECT * FROM pipeline_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return StoredPipelineRun(
            id=int(row["id"]),
            started_at=_str_to_datetime(row["started_at"]),
            completed_at=_str_to_datetime(row["completed_at"]),
            status=row["status"],
            records_fetched=int(row["records_fetched"]),
            records_inserted=int(row["records_inserted"]),
            records_failed=int(row["records_failed"]),
            error_message=row["error_message"],
            created_at=_str_to_datetime(row["created_at"]),
        )

    def list_runs(self, limit: int = 50, offset: int = 0) -> list[StoredPipelineRun]:
        """List pipeline runs ordered by most recent."""
        conn = self.database.connect()
        rows = conn.execute(
            """
            SELECT * FROM pipeline_runs
            ORDER BY started_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return [
            StoredPipelineRun(
                id=int(row["id"]),
                started_at=_str_to_datetime(row["started_at"]),
                completed_at=_str_to_datetime(row["completed_at"]),
                status=row["status"],
                records_fetched=int(row["records_fetched"]),
                records_inserted=int(row["records_inserted"]),
                records_failed=int(row["records_failed"]),
                error_message=row["error_message"],
                created_at=_str_to_datetime(row["created_at"]),
            )
            for row in rows
        ]

    def count_runs(self) -> int:
        """Return total pipeline run count."""
        conn = self.database.connect()
        row = conn.execute("SELECT COUNT(*) AS count FROM pipeline_runs").fetchone()
        return int(row["count"])


class ModelRunRepository:
    """CRUD operations for model training runs."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def create(
        self,
        model_version: str,
        trained_at: datetime,
        training_dataset_size: int | None = None,
        model_parameters: dict | None = None,
        evaluation_metrics: dict | None = None,
        status: str = "completed",
    ) -> int:
        """Record a model training run."""
        conn = self.database.connect()
        cursor = conn.execute(
            """
            INSERT INTO model_runs (
                model_version, trained_at, training_dataset_size,
                model_parameters, evaluation_metrics, status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                model_version,
                _datetime_to_str(trained_at),
                training_dataset_size,
                json.dumps(model_parameters) if model_parameters is not None else None,
                json.dumps(evaluation_metrics) if evaluation_metrics is not None else None,
                status,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)

    def get_by_id(self, run_id: int) -> StoredModelRun | None:
        """Fetch a model run by ID."""
        conn = self.database.connect()
        row = conn.execute(
            "SELECT * FROM model_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return StoredModelRun(
            id=int(row["id"]),
            model_version=row["model_version"],
            trained_at=_str_to_datetime(row["trained_at"]),
            training_dataset_size=row["training_dataset_size"],
            model_parameters=row["model_parameters"],
            evaluation_metrics=row["evaluation_metrics"],
            status=row["status"],
            created_at=_str_to_datetime(row["created_at"]),
        )

    def list_runs(self, limit: int = 50, offset: int = 0) -> list[StoredModelRun]:
        """List model runs ordered by training time."""
        conn = self.database.connect()
        rows = conn.execute(
            """
            SELECT * FROM model_runs
            ORDER BY trained_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return [
            StoredModelRun(
                id=int(row["id"]),
                model_version=row["model_version"],
                trained_at=_str_to_datetime(row["trained_at"]),
                training_dataset_size=row["training_dataset_size"],
                model_parameters=row["model_parameters"],
                evaluation_metrics=row["evaluation_metrics"],
                status=row["status"],
                created_at=_str_to_datetime(row["created_at"]),
            )
            for row in rows
        ]


class AgentRunRepository:
    """CRUD operations for agent workflow runs."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def create(
        self,
        started_at: datetime,
        status: str,
        completed_at: datetime | None = None,
        workflow_name: str | None = None,
        tool_calls_succeeded: int = 0,
        tool_calls_failed: int = 0,
        output_path: str | None = None,
        error_message: str | None = None,
    ) -> int:
        """Record an agent workflow run."""
        conn = self.database.connect()
        cursor = conn.execute(
            """
            INSERT INTO agent_runs (
                started_at, completed_at, status, workflow_name,
                tool_calls_succeeded, tool_calls_failed, output_path, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _datetime_to_str(started_at),
                _datetime_to_str(completed_at),
                status,
                workflow_name,
                tool_calls_succeeded,
                tool_calls_failed,
                output_path,
                error_message,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)

    def get_by_id(self, run_id: int) -> StoredAgentRun | None:
        """Fetch an agent run by ID."""
        conn = self.database.connect()
        row = conn.execute(
            "SELECT * FROM agent_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return StoredAgentRun(
            id=int(row["id"]),
            started_at=_str_to_datetime(row["started_at"]),
            completed_at=_str_to_datetime(row["completed_at"]),
            status=row["status"],
            workflow_name=row["workflow_name"],
            tool_calls_succeeded=int(row["tool_calls_succeeded"]),
            tool_calls_failed=int(row["tool_calls_failed"]),
            output_path=row["output_path"],
            error_message=row["error_message"],
            created_at=_str_to_datetime(row["created_at"]),
        )

    def list_runs(self, limit: int = 50, offset: int = 0) -> list[StoredAgentRun]:
        """List agent runs ordered by start time."""
        conn = self.database.connect()
        rows = conn.execute(
            """
            SELECT * FROM agent_runs
            ORDER BY started_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return [
            StoredAgentRun(
                id=int(row["id"]),
                started_at=_str_to_datetime(row["started_at"]),
                completed_at=_str_to_datetime(row["completed_at"]),
                status=row["status"],
                workflow_name=row["workflow_name"],
                tool_calls_succeeded=int(row["tool_calls_succeeded"]),
                tool_calls_failed=int(row["tool_calls_failed"]),
                output_path=row["output_path"],
                error_message=row["error_message"],
                created_at=_str_to_datetime(row["created_at"]),
            )
            for row in rows
        ]
