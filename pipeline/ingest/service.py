"""Orchestrates fetching, normalization, and storage of job postings."""

import logging
from datetime import datetime, timezone

from pipeline.ingest.client import JobBoardClient
from pipeline.ingest.exceptions import APIRequestError, NormalizationError
from pipeline.ingest.models import IngestionResult
from pipeline.ingest.normalizer import normalize_arbeitnow_job
from pipeline.ingest.storage import JobStorage

logger = logging.getLogger(__name__)


class IngestionService:
    """Fetch jobs from a job board client and persist them to storage."""

    def __init__(self, client: JobBoardClient, storage: JobStorage) -> None:
        self.client = client
        self.storage = storage

    def run(self, max_pages: int | None = None) -> IngestionResult:
        """Execute a full ingestion run with optional page limit."""
        started_at = datetime.now(timezone.utc)
        result = IngestionResult()
        page = 1

        self.storage.init_schema()

        while True:
            if max_pages is not None and page > max_pages:
                break

            try:
                payload = self.client.fetch_page(page)
            except APIRequestError as exc:
                result.pages_failed += 1
                result.error_message = str(exc)
                if result.pages_fetched == 0:
                    result.status = "failed"
                else:
                    result.status = "completed_with_errors"
                logger.error("Stopping ingestion after API failure on page %s", page)
                break

            jobs = payload.get("data", [])
            if not isinstance(jobs, list):
                result.pages_failed += 1
                result.records_failed += 1
                result.error_message = f"Unexpected API payload on page {page}: missing data list"
                result.status = "completed_with_errors" if result.pages_fetched else "failed"
                break

            result.pages_fetched += 1
            ingested_at = datetime.now(timezone.utc)

            for raw_job in jobs:
                if not isinstance(raw_job, dict):
                    result.records_failed += 1
                    logger.warning("Skipping non-dict job record on page %s", page)
                    continue

                result.records_fetched += 1
                try:
                    job = normalize_arbeitnow_job(raw_job, ingested_at=ingested_at)
                    inserted = self.storage.insert_job(job)
                    if inserted:
                        result.records_inserted += 1
                    else:
                        result.records_duplicates += 1
                except NormalizationError as exc:
                    result.records_failed += 1
                    logger.warning("Failed to normalize job on page %s: %s", page, exc)
                except Exception as exc:
                    result.records_failed += 1
                    logger.exception("Unexpected error storing job on page %s: %s", page, exc)

            next_link = payload.get("links", {}).get("next")
            if not next_link:
                break
            page += 1

        if result.status == "completed" and result.pages_failed > 0:
            result.status = "completed_with_errors"

        completed_at = datetime.now(timezone.utc)
        self.storage.record_pipeline_run(started_at, completed_at, result)

        logger.info(
            "Ingestion finished: status=%s fetched=%s inserted=%s duplicates=%s failed=%s pages=%s",
            result.status,
            result.records_fetched,
            result.records_inserted,
            result.records_duplicates,
            result.records_failed,
            result.pages_fetched,
        )
        return result
