"""CLI for the V1 Pipeline Orchestrator."""

import argparse
import json
import logging

from pipeline import initialize
from pipeline.agents.orchestrator.graph import run_orchestrator
from pipeline.config.settings import get_settings
from pipeline.storage.database import Database

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipeline.agents.orchestrator",
        description="Run the full V1 pipeline: Monitor → Analyst → Report Writer.",
    )
    parser.add_argument("--api-url", default=None)
    parser.add_argument("--freshness-hours", type=float, default=None)
    parser.add_argument("--ollama-model", default=None)
    parser.add_argument("--ollama-url", default=None)
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

    logger.info("Starting V1 Pipeline Orchestrator")
    result = run_orchestrator(
        database=database,
        api_base_url=args.api_url or "http://127.0.0.1:8000",
        freshness_threshold_hours=args.freshness_hours or 168.0,
        ollama_model=args.ollama_model or settings.ollama_model,
        ollama_base_url=args.ollama_url or settings.ollama_base_url,
        ollama_timeout=settings.ollama_timeout_seconds,
        report_output_dir=str(settings.report_output_dir),
    )
    database.close()

    logger.info("Orchestrator finished: status=%s agent_run_id=%s",
                result.get("status"), result.get("agent_run_id"))
    print(json.dumps({
        "status": result.get("status"),
        "agent_run_id": result.get("agent_run_id"),
        "tool_calls_succeeded": result.get("tool_calls_succeeded"),
        "tool_calls_failed": result.get("tool_calls_failed"),
        "output_path": result.get("output_path"),
        "error": result.get("error"),
    }, indent=2, default=str))

    return 0 if result.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
