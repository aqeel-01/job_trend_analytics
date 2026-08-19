"""CLI for the V1 Report Writer Agent."""

import argparse
import json
import logging
from pathlib import Path

from pipeline import initialize
from pipeline.agents.report_writer.graph import run_report_writer
from pipeline.config.settings import get_settings

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipeline.agents.report_writer",
        description="Run the V1 Report Writer Agent workflow.",
    )
    parser.add_argument(
        "--analyst-report",
        type=str,
        required=True,
        help="Path to the analyst report JSON file.",
    )
    parser.add_argument("--ollama-model", default=None)
    parser.add_argument("--ollama-url", default=None)
    parser.add_argument("--output", default=None, help="Path to write the markdown report.")
    parser.add_argument("--log-level", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    settings = get_settings()
    if args.log_level:
        settings.log_level = args.log_level
    initialize(settings)

    report_path = Path(args.analyst_report)
    if not report_path.exists():
        logger.error("Analyst report not found: %s", report_path)
        return 1

    with open(report_path) as f:
        analyst_report = json.load(f)

    model = args.ollama_model or settings.ollama_model
    base_url = args.ollama_url or settings.ollama_base_url

    logger.info("Running Report Writer against model=%s url=%s", model, base_url)
    result = run_report_writer(
        analyst_report=analyst_report,
        ollama_model=model,
        ollama_base_url=base_url,
        ollama_timeout=settings.ollama_timeout_seconds,
    )

    logger.info("Report Writer result: status=%s", result.get("status"))

    md = result.get("report_markdown", "")
    if md:
        output_path = args.output
        if output_path is None:
            settings.report_output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(settings.report_output_dir / "latest_report.md")
        Path(output_path).write_text(md, encoding="utf-8")
        logger.info("Report written to %s", output_path)
        print(md)
    else:
        logger.warning("No report generated. Error: %s", result.get("error"))

    return 0 if result.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
