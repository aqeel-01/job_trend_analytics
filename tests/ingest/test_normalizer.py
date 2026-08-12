"""Tests for Arbeitnow job normalization."""

from datetime import datetime, timezone

import pytest

from pipeline.ingest.exceptions import NormalizationError
from pipeline.ingest.models import ARBEITNOW_SOURCE
from pipeline.ingest.normalizer import normalize_arbeitnow_job


def test_normalize_arbeitnow_job_full_record() -> None:
    ingested_at = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    raw = {
        "slug": "software-engineer-berlin-123",
        "company_name": "Example Corp",
        "title": "Software Engineer",
        "description": "<p>Build APIs with Python.</p>",
        "remote": True,
        "url": "https://example.com/jobs/123",
        "location": "Berlin",
        "created_at": 1704067200,
    }

    job = normalize_arbeitnow_job(raw, ingested_at=ingested_at)

    assert job.source_job_id == "software-engineer-berlin-123"
    assert job.title == "Software Engineer"
    assert job.company == "Example Corp"
    assert job.location == "Berlin"
    assert job.description == "<p>Build APIs with Python.</p>"
    assert job.url == "https://example.com/jobs/123"
    assert job.remote is True
    assert job.source == ARBEITNOW_SOURCE
    assert job.ingested_at == ingested_at
    assert job.published_at == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_normalize_arbeitnow_job_optional_fields() -> None:
    raw = {
        "slug": "role-1",
        "company_name": "Co",
        "title": "Role",
        "description": "Desc",
        "url": "https://example.com/1",
        "remote": False,
    }

    job = normalize_arbeitnow_job(raw)

    assert job.location is None
    assert job.remote is False
    assert job.published_at is None


def test_normalize_arbeitnow_job_missing_required_field() -> None:
    with pytest.raises(NormalizationError, match="slug"):
        normalize_arbeitnow_job(
            {
                "company_name": "Co",
                "title": "Role",
                "description": "Desc",
                "url": "https://example.com/1",
            }
        )
