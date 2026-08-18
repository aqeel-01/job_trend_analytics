"""Application settings loaded from environment variables and .env files."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root: parent of the pipeline package directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Runtime configuration for the V1 pipeline."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="JOB_MARKET_",
        extra="ignore",
    )

    app_name: str = "Job Market Intelligence Pipeline"
    environment: str = Field(default="development", description="Runtime environment name.")
    log_level: str = Field(default="INFO", description="Root logger level.")
    log_file: Path | None = Field(
        default=None,
        description="Optional path for file logging. Relative paths resolve from project root.",
    )

    database_path: Path = Field(
        default=PROJECT_ROOT / "data" / "job_market.db",
        description="SQLite database file path.",
    )

    arbeitnow_api_base_url: str = Field(
        default="https://www.arbeitnow.com/api/job-board-api",
        description="Base URL for the Arbeitnow public job board API.",
    )
    ingest_request_timeout_seconds: float = Field(
        default=30.0,
        description="HTTP timeout for ingestion API requests.",
    )
    ingest_max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for failed ingestion API requests.",
    )
    ingest_default_max_pages: int | None = Field(
        default=None,
        description="Default maximum pages to fetch per ingestion run (None = all pages).",
    )
    skills_taxonomy_path: Path = Field(
        default=PROJECT_ROOT / "data" / "skills_taxonomy.json",
        description="Path to the V1 skill taxonomy JSON configuration.",
    )

    @property
    def database_url(self) -> str:
        """SQLite connection URL for SQLAlchemy or similar drivers."""
        resolved = self.database_path
        if not resolved.is_absolute():
            resolved = PROJECT_ROOT / resolved
        return f"sqlite:///{resolved.as_posix()}"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    settings = Settings()
    if not settings.database_path.is_absolute():
        settings.database_path = PROJECT_ROOT / settings.database_path
    if settings.log_file is not None and not settings.log_file.is_absolute():
        settings.log_file = PROJECT_ROOT / settings.log_file
    if not settings.skills_taxonomy_path.is_absolute():
        settings.skills_taxonomy_path = PROJECT_ROOT / settings.skills_taxonomy_path
    return settings
