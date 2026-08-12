"""Arbeitnow public API client."""

import logging
import time
from typing import Protocol

import httpx

from pipeline.ingest.exceptions import APIRequestError

logger = logging.getLogger(__name__)


class JobBoardClient(Protocol):
    """Protocol for fetching paginated job board API responses."""

    def fetch_page(self, page: int) -> dict:
        """Fetch a single page of raw API JSON."""
        ...


class ArbeitnowClient:
    """HTTP client for the Arbeitnow public job board API."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._client = client

    def _request(self, url: str) -> httpx.Response:
        if self._client is not None:
            return self._client.get(url)
        with httpx.Client(timeout=self.timeout_seconds) as client:
            return client.get(url)

    def fetch_page(self, page: int) -> dict:
        """Fetch one page of job listings from Arbeitnow."""
        url = f"{self.base_url}?page={page}"
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._request(url)
                response.raise_for_status()
                payload = response.json()
                logger.info(
                    "Arbeitnow API request succeeded: page=%s status=%s",
                    page,
                    response.status_code,
                )
                return payload
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                logger.error(
                    "Arbeitnow API request failed: page=%s attempt=%s error=%s",
                    page,
                    attempt,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(2 ** (attempt - 1))

        message = f"Failed to fetch Arbeitnow page {page} after {self.max_retries} attempts"
        if last_error is not None:
            message = f"{message}: {last_error}"
        raise APIRequestError(message, page=page)
