"""Command-line interface for the job market intelligence pipeline."""

import argparse
import logging

from pipeline import __version__, initialize
from pipeline.config.settings import get_settings

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the root argument parser."""
    parser = argparse.ArgumentParser(
        prog="pipeline",
        description="AI-Powered Job Market & Skill Demand Intelligence Pipeline (V1).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="Override log level (e.g. DEBUG, INFO, WARNING).",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("info", help="Show application configuration summary.")
    subparsers.add_parser(
        "extract",
        help="Extract skills from stored jobs and populate job_skills table.",
    )

    return parser


def cmd_info() -> None:
    """Print resolved configuration."""
    settings = get_settings()
    logger.info("Application: %s", settings.app_name)
    logger.info("Environment: %s", settings.environment)
    logger.info("Database path: %s", settings.database_path)
    logger.info("Database URL: %s", settings.database_url)
    logger.info("Log level: %s", settings.log_level)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    settings = get_settings()
    if args.log_level:
        settings.log_level = args.log_level
    initialize(settings)

    if args.command == "info":
        cmd_info()
        return 0

    if args.command == "extract":
        from pipeline.extraction.cli import main as extract_main
        return extract_main([])

    if args.command is None:
        parser.print_help()
        return 0

    logger.error("Unknown command: %s", args.command)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
