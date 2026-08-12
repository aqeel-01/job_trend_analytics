"""Job Market & Skill Demand Intelligence Pipeline (V1)."""

from pipeline.config.settings import Settings, get_settings
from pipeline.log_setup import setup_logging

__version__ = "0.1.0"

__all__ = ["__version__", "Settings", "get_settings", "setup_logging", "initialize"]

_initialized = False


def initialize(settings: Settings | None = None) -> Settings:
    """Configure logging and return resolved application settings."""
    global _initialized
    resolved = settings or get_settings()
    setup_logging(level=resolved.log_level, log_file=resolved.log_file)
    _initialized = True
    return resolved


def is_initialized() -> bool:
    """Return whether the application has been initialized."""
    return _initialized
