"""Tests for pipeline run repository."""

from datetime import datetime, timezone

from pipeline.ingest.models import IngestionResult


def test_record_pipeline_run(pipeline_run_repository) -> None:
    started = datetime(2026, 1, 1, tzinfo=timezone.utc)
    completed = datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc)

    run_id = pipeline_run_repository.create(
        started_at=started,
        completed_at=completed,
        status="completed",
        records_fetched=10,
        records_inserted=8,
        records_failed=2,
        error_message=None,
    )

    stored = pipeline_run_repository.get_by_id(run_id)

    assert stored is not None
    assert stored.status == "completed"
    assert stored.records_fetched == 10
    assert stored.records_inserted == 8
    assert stored.records_failed == 2
    assert stored.error_message is None


def test_record_pipeline_run_from_ingestion_result(pipeline_run_repository) -> None:
    started = datetime(2026, 2, 1, tzinfo=timezone.utc)
    completed = datetime(2026, 2, 1, 1, 0, tzinfo=timezone.utc)
    result = IngestionResult(
        records_fetched=5,
        records_inserted=4,
        records_duplicates=1,
        records_failed=0,
        status="completed_with_errors",
        error_message="partial failure",
    )

    run_id = pipeline_run_repository.create_from_ingestion_result(
        started,
        completed,
        result,
    )
    stored = pipeline_run_repository.get_by_id(run_id)

    assert stored is not None
    assert stored.status == "completed_with_errors"
    assert stored.records_fetched == 5
    assert stored.records_inserted == 4
    assert stored.records_failed == 0
    assert stored.error_message == "partial failure"
    assert pipeline_run_repository.count_runs() == 1
