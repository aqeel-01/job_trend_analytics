"""CLI for skill extraction: process all stored jobs and populate job_skills."""

import argparse
import logging

from pipeline import initialize
from pipeline.config.settings import get_settings
from pipeline.extraction.matcher import DeterministicSkillMatcher
from pipeline.extraction.service import SkillExtractionService
from pipeline.skills import load_taxonomy
from pipeline.storage.database import Database
from pipeline.storage.repositories import JobRepository, JobSkillRepository, SkillRepository

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipeline.extract",
        description="Extract skills from stored job descriptions and populate job_skills.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="Jobs to process per batch (default: 200).",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="Override log level.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    settings = get_settings()
    if args.log_level:
        settings.log_level = args.log_level
    initialize(settings)

    taxonomy = load_taxonomy(settings.skills_taxonomy_path)
    database = Database(settings.database_path)
    database.initialize()

    job_repo = JobRepository(database)
    skill_repo = SkillRepository(database)
    job_skill_repo = JobSkillRepository(database)

    matcher = DeterministicSkillMatcher(taxonomy)
    service = SkillExtractionService(
        matcher=matcher,
        skill_repository=skill_repo,
        job_skill_repository=job_skill_repo,
        taxonomy=taxonomy,
    )

    total = job_repo.count_jobs()
    logger.info("Starting extraction for %s jobs", total)

    processed = inserted_total = failed = 0
    offset = 0

    while True:
        batch = job_repo.list_jobs(limit=args.batch_size, offset=offset)
        if not batch:
            break

        for job in batch:
            try:
                result = service.extract_and_store(job.id, job.description)
                inserted_total += len(result.skills)
                processed += 1
            except Exception as exc:
                failed += 1
                logger.warning("Extraction failed for job %s: %s", job.id, exc)

        offset += len(batch)
        logger.info("Progress: %s/%s processed", processed + failed, total)

    database.close()
    logger.info(
        "Extraction complete: jobs=%s skill_links=%s failed=%s",
        processed, inserted_total, failed,
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
