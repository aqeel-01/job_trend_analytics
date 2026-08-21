"""CLI for V1 model retraining and version comparison."""

from __future__ import annotations

import argparse
import json
import logging

from pipeline import initialize
from pipeline.config.settings import get_settings
from pipeline.retraining.service import RetrainingService
from pipeline.storage.database import Database
from pipeline.trend.data import load_weekly_counts

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipeline.retraining",
        description="Train/retrain the V1 trend model and compare versions.",
    )
    sub = parser.add_subparsers(dest="command")

    train = sub.add_parser("train", help="Train or retrain the trend model.")
    train.add_argument(
        "--force",
        action="store_true",
        help="Train even when no new data is detected.",
    )
    train.add_argument(
        "--require-new-data",
        action="store_true",
        help="Skip training when the dataset has not grown.",
    )
    train.add_argument("--version", default=None, help="Override model version string.")

    sub.add_parser("detect", help="Check whether new training data is available.")

    compare = sub.add_parser("compare", help="Compare two model versions.")
    compare.add_argument("--previous", default=None, help="Previous model version (e.g. v1.0).")
    compare.add_argument("--current", default=None, help="Current model version (e.g. v1.1).")
    compare.add_argument("--top-k", type=int, default=10)

    sub.add_parser("list", help="List recent model runs.")
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
    service = RetrainingService(database)

    if args.command == "detect":
        result = service.detect_new_data()
        print(json.dumps(result, indent=2, default=str))
        return 0

    if args.command == "train":
        result = service.train(
            model_version=args.version,
            force=args.force,
            require_new_data=args.require_new_data,
        )
        print(json.dumps(result.to_dict(), indent=2, default=str))
        if not result.skipped and result.previous_version:
            comparison = service.compare_latest()
            if comparison is not None:
                print(json.dumps(comparison.to_dict(), indent=2, default=str))
        return 0 if not result.skipped or args.require_new_data else 0

    if args.command == "compare":
        if args.previous and args.current:
            comparison = service.compare_versions(
                args.previous, args.current, top_k=args.top_k
            )
        else:
            comparison = service.compare_latest(top_k=args.top_k)
            if comparison is None:
                logger.error("Need at least two model runs to compare.")
                return 1
        print(json.dumps(comparison.to_dict(), indent=2, default=str))
        return 0

    if args.command == "list":
        runs = service.model_run_repository.list_runs(limit=20)
        payload = [
            {
                "id": run.id,
                "model_version": run.model_version,
                "trained_at": run.trained_at.isoformat() if run.trained_at else None,
                "training_dataset_size": run.training_dataset_size,
                "status": run.status,
            }
            for run in runs
        ]
        print(json.dumps(payload, indent=2))
        return 0

    # Default: detect → retrain-if-new → compare
    weekly = load_weekly_counts(database)
    detection = service.detect_new_data(weekly_counts=weekly)
    logger.info("New data detection: %s", detection["reason"])
    result = service.retrain_if_new_data(weekly_counts=weekly, force=False)
    print(json.dumps({"detection": detection, "retrain": result.to_dict()}, indent=2, default=str))
    if not result.skipped:
        comparison = service.compare_latest()
        if comparison is not None:
            print(json.dumps(comparison.to_dict(), indent=2, default=str))
    database.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
