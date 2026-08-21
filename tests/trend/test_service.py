"""Tests for trend model run metadata storage."""

from pipeline.storage.repositories import ModelRunRepository
from pipeline.trend.model import TrendModel
from pipeline.trend.service import TrendModelService


def test_model_run_metadata_stored(database) -> None:
    model = TrendModel(model_version="v1.0", min_history_periods=2)
    model_run_repository = ModelRunRepository(database)
    service = TrendModelService(model=model, model_run_repository=model_run_repository)

    weekly = [
        {"Python": 10},
        {"Python": 12},
        {"Python": 20},
    ]
    result, run_id = service.run_and_record(weekly)

    stored = model_run_repository.get_by_id(run_id)
    assert stored is not None
    assert stored.model_version == "v1.0"
    assert stored.training_dataset_size == 10 + 12 + 20
    assert stored.status == "completed"
    assert '"method": "z_score"' in stored.model_parameters
    assert '"skills_ranked": 1' in stored.evaluation_metrics
    assert '"top_skills"' in stored.evaluation_metrics
