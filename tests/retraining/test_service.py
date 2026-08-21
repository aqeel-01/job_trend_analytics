"""Deterministic tests for V1 retraining workflow."""

from pipeline.retraining.service import RetrainingService
from pipeline.storage.repositories import ModelRunRepository


DATASET_V1 = [
    {"Python": 10, "Java": 20, "Go": 5},
    {"Python": 12, "Java": 18, "Go": 6},
    {"Python": 14, "Java": 16, "Go": 7},
]

DATASET_V1_PLUS_NEW = [
    {"Python": 10, "Java": 20, "Go": 5},
    {"Python": 12, "Java": 18, "Go": 6},
    {"Python": 14, "Java": 16, "Go": 7},
    {"Python": 30, "Java": 10, "Go": 8, "Rust": 12},
]


def test_train_initial_model_v1_0(database) -> None:
    service = RetrainingService(database)
    result = service.train(DATASET_V1)

    assert result.skipped is False
    assert result.model_version == "v1.0"
    assert result.previous_version is None
    assert result.status == "completed"
    assert result.training_dataset_size == sum(sum(p.values()) for p in DATASET_V1)
    assert result.period_count == 3
    assert result.model_parameters["method"] == "z_score"
    assert "top_skills" in result.evaluation_metrics

    stored = ModelRunRepository(database).get_by_id(result.run_id)
    assert stored is not None
    assert stored.model_version == "v1.0"
    assert stored.trained_at is not None
    assert stored.training_dataset_size == result.training_dataset_size
    assert stored.model_parameters is not None
    assert stored.evaluation_metrics is not None


def test_retrain_on_new_data_bumps_to_v1_1(database) -> None:
    service = RetrainingService(database)
    first = service.train(DATASET_V1)
    second = service.train(DATASET_V1_PLUS_NEW)

    assert first.model_version == "v1.0"
    assert second.model_version == "v1.1"
    assert second.previous_version == "v1.0"
    assert second.used_new_data is True
    assert second.training_dataset_size > first.training_dataset_size

    latest = ModelRunRepository(database).get_latest()
    assert latest is not None
    assert latest.model_version == "v1.1"


def test_detect_new_data_before_and_after_growth(database) -> None:
    service = RetrainingService(database)
    service.train(DATASET_V1)

    no_growth = service.detect_new_data(weekly_counts=DATASET_V1)
    assert no_growth["has_new_data"] is False
    assert no_growth["latest_model_version"] == "v1.0"

    growth = service.detect_new_data(weekly_counts=DATASET_V1_PLUS_NEW)
    assert growth["has_new_data"] is True
    assert growth["reason"] == "dataset_grew"


def test_retrain_if_new_data_skips_without_growth(database) -> None:
    service = RetrainingService(database)
    service.train(DATASET_V1)
    skipped = service.retrain_if_new_data(DATASET_V1)

    assert skipped.skipped is True
    assert skipped.status == "skipped"
    assert skipped.skip_reason == "no_growth_since_last_train"
    assert ModelRunRepository(database).get_latest().model_version == "v1.0"


def test_retrain_if_new_data_trains_on_growth(database) -> None:
    service = RetrainingService(database)
    service.train(DATASET_V1)
    result = service.retrain_if_new_data(DATASET_V1_PLUS_NEW)

    assert result.skipped is False
    assert result.model_version == "v1.1"


def test_compare_v1_0_to_v1_1(database) -> None:
    service = RetrainingService(database, top_k=3)
    service.train(DATASET_V1)
    service.train(DATASET_V1_PLUS_NEW)

    comparison = service.compare_versions("v1.0", "v1.1", top_k=3)
    assert comparison.previous_version == "v1.0"
    assert comparison.current_version == "v1.1"
    assert comparison.dataset_size_delta is not None
    assert comparison.dataset_size_delta > 0
    assert comparison.current_dataset_size > comparison.previous_dataset_size
    assert "top_skills" in comparison.current_metrics
    assert comparison.summary.startswith("v1.0 → v1.1")

    latest_cmp = service.compare_latest(top_k=3)
    assert latest_cmp is not None
    assert latest_cmp.current_version == "v1.1"


def test_full_workflow_dataset_v1_to_v1_1(database) -> None:
    """Dataset V1 → Model V1.0 → New data → Retrain → Model V1.1 → Compare."""
    service = RetrainingService(database, top_k=5)

    # Dataset V1 → Model V1.0
    v1 = service.train(DATASET_V1, model_version="v1.0")
    assert v1.model_version == "v1.0"

    # New data detection
    detection = service.detect_new_data(DATASET_V1_PLUS_NEW)
    assert detection["has_new_data"] is True

    # Retrain → Model V1.1
    v11 = service.retrain_if_new_data(DATASET_V1_PLUS_NEW)
    assert v11.model_version == "v1.1"

    # Compare
    comparison = service.compare_versions("v1.0", "v1.1")
    assert comparison.previous_run_id == v1.run_id
    assert comparison.current_run_id == v11.run_id
    assert comparison.dataset_size_delta == (
        v11.training_dataset_size - v1.training_dataset_size
    )

    runs = ModelRunRepository(database).list_runs()
    versions = [run.model_version for run in runs]
    assert versions == ["v1.1", "v1.0"]
