"""Job ingestion from external APIs."""

from pipeline.ingest.models import IngestionResult, JobPosting

__all__ = ["IngestionResult", "JobPosting", "IngestionService"]


def __getattr__(name: str):
    if name == "IngestionService":
        from pipeline.ingest.service import IngestionService

        return IngestionService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
