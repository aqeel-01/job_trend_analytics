"""Run trend model and persist model-run metadata."""

from datetime import datetime, timezone

from pipeline.storage.repositories import ModelRunRepository
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
        result = self.model.compute(weekly_counts)

        total_mentions = sum(
            score.current_mentions for score in result.skills
        )
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
            evaluation_metrics={
                "skills_ranked": len(result.skills),
                "rising_skills": sum(
                    1 for skill in result.skills if skill.trend.value == "rising"
                ),
                "falling_skills": sum(
                    1 for skill in result.skills if skill.trend.value == "falling"
                ),
            },
            status="completed",
        )
        return result, run_id
