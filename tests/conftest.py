"""Shared pytest fixtures."""

import logging

import pytest

import pipeline
from pipeline.config.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def reset_application_state() -> None:
    """Reset cached settings, logging, and init flag between tests."""
    get_settings.cache_clear()
    pipeline._initialized = False

    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()

    yield

    get_settings.cache_clear()
    pipeline._initialized = False


@pytest.fixture
def test_settings(tmp_path) -> Settings:
    """Provide settings pointed at a temporary database path."""
    db_path = tmp_path / "test.db"
    return Settings(database_path=db_path, log_level="DEBUG")


@pytest.fixture
def database(test_settings: Settings):
    """Provide an initialized temporary SQLite database."""
    from pipeline.storage.database import Database

    db = Database(test_settings.database_path)
    db.initialize()
    yield db
    db.close()


@pytest.fixture
def job_repository(database):
    """Provide a job repository bound to the temporary database."""
    from pipeline.storage.repositories import JobRepository

    return JobRepository(database)


@pytest.fixture
def pipeline_run_repository(database):
    """Provide a pipeline run repository bound to the temporary database."""
    from pipeline.storage.repositories import PipelineRunRepository

    return PipelineRunRepository(database)
