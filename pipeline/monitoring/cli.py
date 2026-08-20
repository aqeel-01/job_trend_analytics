"""CLI for inspecting V1 monitoring metrics."""

import argparse
import json
import logging

from pipeline import initialize
from pipeline.config.settings import get_settings
from pipeline.monitoring.store import get_metrics_store, reset_metrics_store

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipeline.monitoring",
        description="Inspect V1 local monitoring metrics.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print an aggregated metrics summary (default).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_events",
        help="Print all raw metric events as JSON.",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Filter events by metric name.",
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

    reset_metrics_store()
    store = get_metrics_store(settings.metrics_path)

    if args.list_events:
        events = store.filter(args.name) if args.name else store.read_all()
        print(json.dumps([e.to_dict() for e in events], indent=2))
        return 0

    summary = store.summary()
    if args.name:
        events = store.filter(args.name)
        print(json.dumps({
            "name": args.name,
            "count": len(events),
            "events": [e.to_dict() for e in events],
        }, indent=2))
    else:
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
