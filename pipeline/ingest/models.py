"""Internal job representation and ingestion result types."""

from dataclasses import dataclass
from datetime import datetime

ARBEITNOW_SOURCE = "arbeitnow"


@dataclass(frozen=True)
class JobPosting:
    """Normalized job posting from an external source."""

    source_job_id: str
    title: str
    company: str
    location: str | None
    description: str
    url: str
    published_at: datetime | None
    remote: bool | None
    source: str
    ingested_at: datetime


@dataclass
class IngestionResult:
    """Summary of a single ingestion run."""

    records_fetched: int = 0
    records_inserted: int = 0
    records_duplicates: int = 0
    records_failed: int = 0
    pages_fetched: int = 0
    pages_failed: int = 0
    status: str = "completed"
    error_message: str | None = None
