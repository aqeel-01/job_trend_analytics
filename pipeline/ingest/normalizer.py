"""Normalize Arbeitnow API records into internal job postings."""

from datetime import datetime, timezone

from pipeline.ingest.exceptions import NormalizationError
from pipeline.ingest.models import ARBEITNOW_SOURCE, JobPosting


def _parse_unix_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def normalize_arbeitnow_job(
    raw: dict,
    ingested_at: datetime | None = None,
) -> JobPosting:
    """Map an Arbeitnow API job object to the internal JobPosting model."""
    source_job_id = raw.get("slug")
    title = raw.get("title")
    company = raw.get("company_name")
    description = raw.get("description")
    url = raw.get("url")

    if not source_job_id:
        raise NormalizationError("Missing required field: slug")
    if not title:
        raise NormalizationError("Missing required field: title")
    if not company:
        raise NormalizationError("Missing required field: company_name")
    if not description:
        raise NormalizationError("Missing required field: description")
    if not url:
        raise NormalizationError("Missing required field: url")

    location = raw.get("location")
    remote_value = raw.get("remote")
    remote: bool | None
    if remote_value is None:
        remote = None
    else:
        remote = bool(remote_value)

    published_at = _parse_unix_timestamp(raw.get("created_at"))
    resolved_ingested_at = ingested_at or datetime.now(timezone.utc)

    return JobPosting(
        source_job_id=str(source_job_id),
        title=str(title).strip(),
        company=str(company).strip(),
        location=str(location).strip() if location else None,
        description=str(description),
        url=str(url).strip(),
        published_at=published_at,
        remote=remote,
        source=ARBEITNOW_SOURCE,
        ingested_at=resolved_ingested_at,
    )
