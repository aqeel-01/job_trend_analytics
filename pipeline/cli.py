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

    # Delegated commands: disable local --help so flags (including --help) are
    # forwarded to the subcommand CLI via parse_known_args.
    for name, help_text in (
        ("extract", "Extract skills from stored jobs and populate job_skills table."),
        ("monitor", "Run the V1 Monitor Agent workflow."),
        ("analyst", "Run the V1 Analyst Agent workflow."),
        ("report", "Run the V1 Report Writer Agent workflow."),
        ("run", "Run the full V1 pipeline orchestrator (Monitor → Analyst → Report)."),
        ("metrics", "Show V1 monitoring metrics summary."),
        ("retrain", "Detect new data, retrain the V1 trend model, and compare versions."),
    ):
        subparsers.add_parser(name, help=help_text, add_help=False)

    return parser


def cmd_info() -> None:
    """Print resolved configuration."""
    settings = get_settings()
    logger.info("Application: %s", settings.app_name)
    logger.info("Environment: %s", settings.environment)
    logger.info("Database path: %s", settings.database_path)
    logger.info("Database URL: %s", settings.database_url)
    logger.info("Log level: %s", settings.log_level)
    logger.info("Ollama URL: %s", settings.ollama_base_url)
    logger.info("Ollama model: %s", settings.ollama_model)
    logger.info("Report output dir: %s", settings.report_output_dir)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Unknown args after the subcommand are forwarded to that subcommand's CLI
    (e.g. ``pipeline report --ollama-model deepseek-r1:7b``).
    """
    parser = build_parser()
    args, remaining = parser.parse_known_args(argv)

    settings = get_settings()
    if args.log_level:
        settings.log_level = args.log_level
    initialize(settings)

    if args.command == "info":
        cmd_info()
        return 0

    if args.command == "extract":
        from pipeline.extraction.cli import main as extract_main
        return extract_main(remaining)

    if args.command == "monitor":
        from pipeline.agents.monitor.cli import main as monitor_main
        return monitor_main(remaining)

    if args.command == "analyst":
        from pipeline.agents.analyst.cli import main as analyst_main
        return analyst_main(remaining)

    if args.command == "report":
        from pipeline.agents.report_writer.cli import main as report_main
        return report_main(remaining)

    if args.command == "run":
        from pipeline.agents.orchestrator.cli import main as orchestrator_main
        return orchestrator_main(remaining)

    if args.command == "metrics":
        from pipeline.monitoring.cli import main as metrics_main
        # Default to summary when no args provided; otherwise forward flags.
        return metrics_main(remaining if remaining else ["--summary"])

    if args.command == "retrain":
        from pipeline.retraining.cli import main as retrain_main
        return retrain_main(remaining)

    if args.command is None:
        parser.print_help()
        return 0

    logger.error("Unknown command: %s", args.command)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
