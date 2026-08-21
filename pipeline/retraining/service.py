"""V1 retraining workflow: detect new data → retrain → version → persist."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from pipeline.monitoring.recorder import record_model_execution_time
from pipeline.retraining.comparison import compare_model_runs
from pipeline.retraining.models import ModelVersionComparison, RetrainResult
from pipeline.retraining.versioning import bump_minor_version, initial_version
from pipeline.storage.database import Database
from pipeline.storage.repositories import ModelRunRepository
from pipeline.trend.data import dataset_fingerprint, detect_new_data, load_weekly_counts
from pipeline.trend.metrics import build_evaluation_metrics
from pipeline.trend.model import TrendModel
from pipeline.trend.models import TrendModelResult

logger = logging.getLogger(__name__)


class RetrainingService:
    """Train/retrain the V1 trend model and compare versions."""

    def __init__(
        self,
        database: Database,
        model_run_repository: ModelRunRepository | None = None,
        min_history_periods: int = 2,
        z_rising_threshold: float = 0.5,
        z_falling_threshold: float = -0.5,
        top_k: int = 10,
    ) -> None:
        self.database = database
        self.model_run_repository = model_run_repository or ModelRunRepository(database)
        self.min_history_periods = min_history_periods
        self.z_rising_threshold = z_rising_threshold
        self.z_falling_threshold = z_falling_threshold
        self.top_k = top_k

    def detect_new_data(
        self,
        weekly_counts: list[dict[str, int]] | None = None,
    ) -> dict:
        """Return whether the stored dataset has grown since the last model run."""
        return detect_new_data(
            self.database,
            model_run_repository=self.model_run_repository,
            weekly_counts=weekly_counts,
        )

    def train(
        self,
        weekly_counts: list[dict[str, int]] | None = None,
        *,
        model_version: str | None = None,
        force: bool = False,
        require_new_data: bool = False,
    ) -> RetrainResult:
        """
        Train (or retrain) the V1 trend model and persist model-run metadata.

        - First run → ``v1.0``
        - Subsequent runs → bump minor version (``v1.1``, ``v1.2``, ...)
        - If ``require_new_data`` and no growth is detected, skip unless ``force``.
        """
        weekly = weekly_counts if weekly_counts is not None else load_weekly_counts(self.database)
        fingerprint = dataset_fingerprint(weekly)
        latest = self.model_run_repository.get_latest()
        previous_version = latest.model_version if latest is not None else None

        new_data = self.detect_new_data(weekly_counts=weekly)
        used_new_data = bool(new_data["has_new_data"])

        if require_new_data and not used_new_data and not force:
            trained_at = datetime.now(timezone.utc)
            return RetrainResult(
                run_id=-1,
                model_version=previous_version or initial_version(),
                previous_version=previous_version,
                trained_at=trained_at,
                training_dataset_size=fingerprint["total_mentions"],
                period_count=fingerprint["period_count"],
                model_parameters={},
                evaluation_metrics={},
                status="skipped",
                used_new_data=False,
                skipped=True,
                skip_reason=new_data["reason"],
            )

        if model_version is None:
            version = (
                initial_version()
                if previous_version is None
                else bump_minor_version(previous_version)
            )
        else:
            version = model_version

        model = TrendModel(
            model_version=version,
            min_history_periods=self.min_history_periods,
            z_rising_threshold=self.z_rising_threshold,
            z_falling_threshold=self.z_falling_threshold,
        )

        started = time.monotonic()
        try:
            result = model.compute(weekly)
            record_model_execution_time(
                duration_seconds=time.monotonic() - started,
                success=True,
                model_version=version,
            )
        except Exception as exc:
            record_model_execution_time(
                duration_seconds=time.monotonic() - started,
                success=False,
                model_version=version,
                detail=str(exc),
            )
            raise

        parameters = {
            "method": "z_score",
            "min_history_periods": model.min_history_periods,
            "z_rising_threshold": model.z_rising_threshold,
            "z_falling_threshold": model.z_falling_threshold,
            "period_count": result.period_count,
            "unique_skills": fingerprint["unique_skills"],
        }
        metrics = build_evaluation_metrics(result, top_k=self.top_k)
        dataset_size = fingerprint["total_mentions"]

        run_id = self.model_run_repository.create(
            model_version=version,
            trained_at=result.generated_at,
            training_dataset_size=dataset_size,
            model_parameters=parameters,
            evaluation_metrics=metrics,
            status="completed",
        )
        logger.info(
            "Model trained: version=%s run_id=%s dataset_size=%s periods=%s previous=%s",
            version,
            run_id,
            dataset_size,
            result.period_count,
            previous_version,
        )

        return RetrainResult(
            run_id=run_id,
            model_version=version,
            previous_version=previous_version,
            trained_at=result.generated_at,
            training_dataset_size=dataset_size,
            period_count=result.period_count,
            model_parameters=parameters,
            evaluation_metrics=metrics,
            status="completed",
            used_new_data=used_new_data or previous_version is None,
            skipped=False,
        )

    def retrain_if_new_data(
        self,
        weekly_counts: list[dict[str, int]] | None = None,
        *,
        force: bool = False,
    ) -> RetrainResult:
        """Retrain only when new data is detected (or ``force=True``)."""
        return self.train(
            weekly_counts=weekly_counts,
            force=force,
            require_new_data=True,
        )

    def compare_latest(self, *, top_k: int | None = None) -> ModelVersionComparison | None:
        """Compare the two most recent model runs, if both exist."""
        runs = self.model_run_repository.list_runs(limit=2)
        if len(runs) < 2:
            return None
        current, previous = runs[0], runs[1]
        return compare_model_runs(
            previous,
            current,
            top_k=top_k or self.top_k,
        )

    def compare_versions(
        self,
        previous_version: str,
        current_version: str,
        *,
        top_k: int | None = None,
    ) -> ModelVersionComparison:
        """Compare two named model versions from SQLite."""
        previous = self.model_run_repository.get_by_version(previous_version)
        current = self.model_run_repository.get_by_version(current_version)
        if previous is None:
            raise ValueError(f"Model version not found: {previous_version}")
        if current is None:
            raise ValueError(f"Model version not found: {current_version}")
        return compare_model_runs(previous, current, top_k=top_k or self.top_k)
