"""Job ingestion from external APIs."""

from pipeline.ingest.models import IngestionResult, JobPosting
from pipeline.ingest.service import IngestionService

__all__ = ["IngestionResult", "JobPosting", "IngestionService"]
