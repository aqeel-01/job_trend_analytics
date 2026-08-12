"""Tests proving the project initializes correctly."""

import logging

import pytest

from pipeline import __version__, initialize, is_initialized
from pipeline.config.settings import Settings, get_settings, PROJECT_ROOT


def test_package_version() -> None:
    assert __version__ == "0.1.0"


def test_settings_defaults() -> None:
    settings = get_settings()
    assert settings.app_name == "Job Market Intelligence Pipeline"
    assert settings.environment == "development"
    assert settings.log_level == "INFO"
    assert settings.database_path.name == "job_market.db"
    assert settings.database_path.parent.name == "data"
    assert settings.database_url.startswith("sqlite:///")


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    db_path = tmp_path / "custom.db"
    monkeypatch.setenv("JOB_MARKET_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("JOB_MARKET_LOG_LEVEL", "WARNING")
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.database_path == db_path
    assert settings.log_level == "WARNING"


def test_initialize_configures_logging(test_settings: Settings) -> None:
    settings = initialize(test_settings)
    assert is_initialized()
    assert settings.log_level == "DEBUG"

    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) >= 1

    pipeline_logger = logging.getLogger("pipeline")
    assert pipeline_logger.level == logging.DEBUG


def test_project_root_resolves() -> None:
    assert PROJECT_ROOT.is_dir()
    assert (PROJECT_ROOT / "pipeline").is_dir()
