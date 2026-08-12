"""Exceptions raised during job ingestion."""

class IngestionError(Exception):
    """Base exception for ingestion failures."""


class APIRequestError(IngestionError):
    """Raised when an external API request fails after retries."""

    def __init__(self, message: str, page: int | None = None) -> None:
        super().__init__(message)
        self.page = page


class NormalizationError(IngestionError):
    """Raised when an API record cannot be normalized."""
