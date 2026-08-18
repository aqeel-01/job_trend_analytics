"""Tests for job repository operations."""

from datetime import datetime, timezone

from pipeline.ingest.models import ARBEITNOW_SOURCE, JobPosting


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


def test_insert_job(job_repository) -> None:
    result = job_repository.insert_job(_sample_job())

    assert result.inserted is True
    assert result.job_id == 1
    assert job_repository.count_jobs() == 1


def test_duplicate_job_is_ignored(job_repository) -> None:
    first = job_repository.insert_job(_sample_job())
    second = job_repository.insert_job(_sample_job())

    assert first.inserted is True
    assert second.inserted is False
    assert second.job_id == first.job_id
    assert job_repository.exists(ARBEITNOW_SOURCE, "job-1")
    assert job_repository.count_jobs() == 1


def test_get_job_by_id(job_repository) -> None:
    insert_result = job_repository.insert_job(_sample_job())
    stored = job_repository.get_by_id(insert_result.job_id)

    assert stored is not None
    assert stored.id == insert_result.job_id
    assert stored.source_job_id == "job-1"
    assert stored.title == "Software Engineer"
    assert stored.company == "Example Corp"
    assert stored.remote is True


def test_get_job_by_source_job_id(job_repository) -> None:
    job_repository.insert_job(_sample_job())
    stored = job_repository.get_by_source_job_id(ARBEITNOW_SOURCE, "job-1")

    assert stored is not None
    assert stored.source_job_id == "job-1"
    assert stored.source == ARBEITNOW_SOURCE


def test_list_jobs_with_source_filter(job_repository) -> None:
    job_repository.insert_job(_sample_job("job-1"))
    job_repository.insert_job(_sample_job("job-2"))

    all_jobs = job_repository.list_jobs()
    filtered = job_repository.list_jobs(source=ARBEITNOW_SOURCE)

    assert len(all_jobs) == 2
    assert len(filtered) == 2
    assert job_repository.count_jobs(source=ARBEITNOW_SOURCE) == 2


def test_delete_job(job_repository) -> None:
    result = job_repository.insert_job(_sample_job())
    deleted = job_repository.delete_by_id(result.job_id)

    assert deleted is True
    assert job_repository.get_by_id(result.job_id) is None
    assert job_repository.count_jobs() == 0
