"""Tests for skill extraction persistence and evaluation dataset."""

from datetime import datetime, timezone

import pytest

from pipeline.skills import load_taxonomy
from pipeline.extraction.matcher import DeterministicSkillMatcher
from pipeline.extraction.models import EXTRACTION_METHOD_DETERMINISTIC
from pipeline.extraction.service import SkillExtractionService, load_evaluation_dataset
from pipeline.ingest.models import ARBEITNOW_SOURCE, JobPosting
from pipeline.storage.repositories import JobRepository, JobSkillRepository, SkillRepository


@pytest.fixture
def extraction_service(database, job_repository) -> SkillExtractionService:
    taxonomy = load_taxonomy()
    matcher = DeterministicSkillMatcher(taxonomy)
    skill_repository = SkillRepository(database)
    job_skill_repository = JobSkillRepository(database)
    return SkillExtractionService(
        matcher=matcher,
        skill_repository=skill_repository,
        job_skill_repository=job_skill_repository,
        taxonomy=taxonomy,
    )


def _insert_job(job_repository: JobRepository, source_job_id: str = "job-1") -> int:
    job = JobPosting(
        source_job_id=source_job_id,
        title="Engineer",
        company="Example Corp",
        location="Berlin",
        description="placeholder",
        url="https://example.com/jobs/1",
        published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        remote=True,
        source=ARBEITNOW_SOURCE,
        ingested_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    result = job_repository.insert_job(job)
    assert result.job_id is not None
    return result.job_id


def test_extract_and_store_persists_skills_and_links(
    extraction_service: SkillExtractionService,
    job_repository: JobRepository,
    database,
) -> None:
    job_id = _insert_job(job_repository)
    description = "Backend role using Python, Docker, and AWS in production."

    result = extraction_service.extract_and_store(job_id, description)

    assert {skill.canonical_name for skill in result.skills} == {
        "Python",
        "Docker",
        "AWS",
    }

    skill_repository = SkillRepository(database)
    job_skill_repository = JobSkillRepository(database)

    assert skill_repository.count_skills() == 3
    links = job_skill_repository.get_for_job(job_id)
    assert len(links) == 3
    assert all(link.extraction_method == EXTRACTION_METHOD_DETERMINISTIC for link in links)
    assert all(link.confidence is not None for link in links)


def test_extract_and_store_is_idempotent_for_job_skills(
    extraction_service: SkillExtractionService,
    job_repository: JobRepository,
    database,
) -> None:
    job_id = _insert_job(job_repository)
    description = "Python and Docker required."

    extraction_service.extract_and_store(job_id, description)
    extraction_service.extract_and_store(job_id, description)

    job_skill_repository = JobSkillRepository(database)
    assert job_skill_repository.count_for_job(job_id) == 2


def test_evaluation_dataset_structure_loads() -> None:
    dataset = load_evaluation_dataset()

    assert dataset.version == "1.0"
    assert dataset.target_sample_count == "20-50"
    assert dataset.metrics == ("precision", "recall", "f1")
    assert len(dataset.samples) >= 3

    for sample in dataset.samples:
        assert sample.id
        assert sample.description
        assert sample.labeled_skills == ()
