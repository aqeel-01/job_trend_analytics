"""CLI for the V1 Monitor Agent."""

import argparse
import json
import logging

from pipeline import initialize
from pipeline.agents.monitor.graph import run_monitor
from pipeline.config.settings import get_settings
from pipeline.storage.database import Database

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipeline.agents.monitor",
        description="Run the V1 Monitor Agent workflow.",
    )
    parser.add_argument(
        "--freshness-hours",
        type=float,
        default=168.0,
        help="Hours before pipeline data is considered stale (default: 168 = 7 days).",
    )
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000",
        help="Base URL for the FastAPI health check.",
    )
    parser.add_argument("--log-level", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    settings = get_settings()
    if args.log_level:
        settings.log_level = args.log_level
    initialize(settings)

    database = Database(settings.database_path)
    database.initialize()

    logger.info("Running Monitor Agent workflow")
    result = run_monitor(
        database,
        freshness_threshold_hours=args.freshness_hours,
        api_base_url=args.api_url,
    )
    database.close()

    logger.info("Monitor result: status=%s", result.get("status"))
    logger.info("  db_healthy=%s pipeline_fresh=%s api_healthy=%s",
                result.get("db_healthy"), result.get("pipeline_fresh"), result.get("api_healthy"))
    logger.info("  new_data=%s ingestion_failure=%s should_trigger=%s",
                result.get("new_data_exists"), result.get("ingestion_failure"),
                result.get("should_trigger_analysis"))

    if result.get("error"):
        logger.warning("  error: %s", result["error"])

    print(json.dumps({k: v for k, v in result.items() if k != "tool_results"}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
