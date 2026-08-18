"""CLI for job data ingestion."""

import argparse
import logging

from pipeline import initialize
from pipeline.config.settings import get_settings
from pipeline.ingest.client import ArbeitnowClient
from pipeline.ingest.service import IngestionService
from pipeline.storage.database import Database
from pipeline.storage.repositories import JobRepository, PipelineRunRepository

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the ingestion CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="pipeline.ingest",
        description="Fetch job postings from Arbeitnow and store them in SQLite.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Maximum API pages to fetch (default: all available pages).",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="Override log level (e.g. DEBUG, INFO, WARNING).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run job ingestion from the command line."""
    parser = build_parser()
    args = parser.parse_args(argv)

    settings = get_settings()
    if args.log_level:
        settings.log_level = args.log_level
    initialize(settings)

    max_pages = args.max_pages if args.max_pages is not None else settings.ingest_default_max_pages

    client = ArbeitnowClient(
        base_url=settings.arbeitnow_api_base_url,
        timeout_seconds=settings.ingest_request_timeout_seconds,
        max_retries=settings.ingest_max_retries,
    )
    database = Database(settings.database_path)
    job_repository = JobRepository(database)
    pipeline_run_repository = PipelineRunRepository(database)
    service = IngestionService(
        client=client,
        job_repository=job_repository,
        pipeline_run_repository=pipeline_run_repository,
        database=database,
    )

    try:
        result = service.run(max_pages=max_pages)
    finally:
        database.close()

    if result.status == "failed":
        logger.error("Ingestion failed: %s", result.error_message)
        return 1

    logger.info(
        "Ingestion complete: inserted=%s duplicates=%s failed=%s",
        result.records_inserted,
        result.records_duplicates,
        result.records_failed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
