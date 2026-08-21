"""Run trend model and persist model-run metadata."""

import time

from pipeline.monitoring.recorder import record_model_execution_time
from pipeline.storage.repositories import ModelRunRepository
from pipeline.trend.metrics import build_evaluation_metrics
from pipeline.trend.model import TrendModel
from pipeline.trend.models import TrendModelResult


class TrendModelService:
    """Execute the V1 trend model and record run metadata in SQLite."""

    def __init__(
        self,
        model: TrendModel,
        model_run_repository: ModelRunRepository,
    ) -> None:
        self.model = model
        self.model_run_repository = model_run_repository

    def run_and_record(
        self,
        weekly_counts: list[dict[str, int]],
    ) -> tuple[TrendModelResult, int]:
        """Compute trends and store a model_runs row per SRS requirements."""
        started = time.monotonic()
        try:
            result = self.model.compute(weekly_counts)
            record_model_execution_time(
                duration_seconds=time.monotonic() - started,
                success=True,
                model_version=result.model_version,
            )
        except Exception as exc:
            record_model_execution_time(
                duration_seconds=time.monotonic() - started,
                success=False,
                detail=str(exc),
            )
            raise

        total_mentions = sum(sum(period.values()) for period in weekly_counts)
        run_id = self.model_run_repository.create(
            model_version=result.model_version,
            trained_at=result.generated_at,
            training_dataset_size=total_mentions,
            model_parameters={
                "method": "z_score",
                "min_history_periods": self.model.min_history_periods,
                "z_rising_threshold": self.model.z_rising_threshold,
                "z_falling_threshold": self.model.z_falling_threshold,
                "period_count": result.period_count,
            },
            evaluation_metrics=build_evaluation_metrics(result),
            status="completed",
        )
        return result, run_id
