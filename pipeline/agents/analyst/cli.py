"""CLI for the V1 Analyst Agent."""

import argparse
import json
import logging
from pathlib import Path

from pipeline import initialize
from pipeline.agents.analyst.graph import run_analyst
from pipeline.config.settings import get_settings

logger = logging.getLogger(__name__)

DEFAULT_ANALYST_REPORT_NAME = "latest_analyst.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipeline.agents.analyst",
        description="Run the V1 Analyst Agent workflow.",
    )
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000",
        help="Base URL for the FastAPI ML endpoint.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max skills to retrieve from the trending endpoint.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write the analyst report JSON (default: reports/latest_analyst.json).",
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

    logger.info("Running Analyst Agent workflow against %s", args.api_url)
    result = run_analyst(api_base_url=args.api_url, trending_limit=args.limit)

    logger.info("Analyst result: status=%s", result.get("status"))

    report = result.get("report")
    if report:
        logger.info("  strong_signals=%d weak_signals=%d risers=%d fallers=%d",
                     len(report.get("strong_signals", [])),
                     len(report.get("weak_signals", [])),
                     len(report.get("top_risers", [])),
                     len(report.get("top_fallers", [])))
        settings.report_output_dir.mkdir(parents=True, exist_ok=True)
        output_path = Path(args.output) if args.output else (
            settings.report_output_dir / DEFAULT_ANALYST_REPORT_NAME
        )
        output_path.write_text(
            json.dumps(report, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info("Analyst report written to %s", output_path)
        print(json.dumps(report, indent=2, default=str))
    else:
        logger.warning("  error: %s", result.get("error"))
        print(json.dumps({"status": result.get("status"), "error": result.get("error")}, indent=2))

    return 0 if result.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
