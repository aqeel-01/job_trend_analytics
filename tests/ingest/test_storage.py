"""Tests for SQLite job storage."""

from datetime import datetime, timezone

from pipeline.ingest.models import ARBEITNOW_SOURCE, JobPosting
from pipeline.ingest.storage import JobStorage


def _sample_job(source_job_id: str = "job-1") -> JobPosting:
    return JobPosting(
        source_job_id=source_job_id,
        title="Software Engineer",
        company="Example Corp",
        location="Berlin",
        description="Build APIs",
        url="https://example.com/jobs/1",
        published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        remote=True,
        source=ARBEITNOW_SOURCE,
        ingested_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_insert_job_and_count(test_settings) -> None:
    storage = JobStorage(test_settings.database_path)
    storage.init_schema()

    inserted = storage.insert_job(_sample_job())
    duplicate = storage.insert_job(_sample_job())

    assert inserted is True
    assert duplicate is False
    assert storage.count_jobs() == 1
    assert storage.count_jobs(source=ARBEITNOW_SOURCE) == 1

    storage.close()


def test_record_pipeline_run(test_settings) -> None:
    storage = JobStorage(test_settings.database_path)
    storage.init_schema()

    from pipeline.ingest.models import IngestionResult

    started = datetime(2026, 1, 1, tzinfo=timezone.utc)
    completed = datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc)
    result = IngestionResult(
        records_fetched=10,
        records_inserted=8,
        records_failed=2,
        status="completed",
    )

    run_id = storage.record_pipeline_run(started, completed, result)
    assert run_id == 1

    storage.close()
