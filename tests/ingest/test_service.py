"""Tests for ingestion service orchestration."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pipeline.ingest.exceptions import APIRequestError
from pipeline.ingest.service import IngestionService
from pipeline.ingest.storage import JobStorage


FIXTURES = Path(__file__).parent.parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class MockJobBoardClient:
    def __init__(self, pages: dict[int, dict], fail_page: int | None = None) -> None:
        self.pages = pages
        self.fail_page = fail_page
        self.calls: list[int] = []

    def fetch_page(self, page: int) -> dict:
        self.calls.append(page)
        if self.fail_page == page:
            raise APIRequestError(f"simulated failure on page {page}", page=page)
        if page not in self.pages:
            return {"data": [], "links": {"next": None}}
        return self.pages[page]


def test_ingestion_service_inserts_jobs(test_settings) -> None:
    page_one = _load_fixture("arbeitnow_page.json")
    storage = JobStorage(test_settings.database_path)
    client = MockJobBoardClient({1: page_one})
    service = IngestionService(client=client, storage=storage)

    result = service.run()

    assert result.status == "completed"
    assert result.pages_fetched == 1
    assert result.records_fetched == 2
    assert result.records_inserted == 2
    assert result.records_duplicates == 0
    assert result.records_failed == 0
    assert storage.count_jobs() == 2

    storage.close()


def test_ingestion_service_skips_duplicates(test_settings) -> None:
    page_one = _load_fixture("arbeitnow_page.json")
    storage = JobStorage(test_settings.database_path)
    client = MockJobBoardClient({1: page_one})
    service = IngestionService(client=client, storage=storage)

    first = service.run()
    second = service.run()

    assert first.records_inserted == 2
    assert second.records_inserted == 0
    assert second.records_duplicates == 2
    assert storage.count_jobs() == 2

    storage.close()


def test_ingestion_service_paginates(test_settings) -> None:
    page_one = _load_fixture("arbeitnow_page.json")
    page_two = _load_fixture("arbeitnow_page_2.json")
    page_one["links"]["next"] = "https://www.arbeitnow.com/api/job-board-api?page=2"

    storage = JobStorage(test_settings.database_path)
    client = MockJobBoardClient({1: page_one, 2: page_two})
    service = IngestionService(client=client, storage=storage)

    result = service.run()

    assert result.pages_fetched == 2
    assert result.records_inserted == 3
    assert client.calls == [1, 2]

    storage.close()


def test_ingestion_service_handles_api_failure(test_settings) -> None:
    page_one = _load_fixture("arbeitnow_page.json")
    storage = JobStorage(test_settings.database_path)
    client = MockJobBoardClient({1: page_one}, fail_page=1)
    service = IngestionService(client=client, storage=storage)

    result = service.run()

    assert result.status == "failed"
    assert result.pages_fetched == 0
    assert result.records_inserted == 0
    assert result.error_message is not None

    storage.close()


def test_ingestion_service_max_pages_limit(test_settings) -> None:
    page_one = _load_fixture("arbeitnow_page.json")
    page_two = _load_fixture("arbeitnow_page_2.json")
    page_one["links"]["next"] = "https://www.arbeitnow.com/api/job-board-api?page=2"

    storage = JobStorage(test_settings.database_path)
    client = MockJobBoardClient({1: page_one, 2: page_two})
    service = IngestionService(client=client, storage=storage)

    result = service.run(max_pages=1)

    assert result.pages_fetched == 1
    assert result.records_inserted == 2
    assert client.calls == [1]

    storage.close()


def test_ingestion_service_normalization_failure(test_settings) -> None:
    payload = {
        "data": [
            {"slug": "bad", "company_name": "Co"},
            _load_fixture("arbeitnow_page.json")["data"][0],
        ],
        "links": {"next": None},
    }
    storage = JobStorage(test_settings.database_path)
    client = MockJobBoardClient({1: payload})
    service = IngestionService(client=client, storage=storage)

    result = service.run()

    assert result.records_fetched == 2
    assert result.records_failed == 1
    assert result.records_inserted == 1
    assert result.status == "completed"

    storage.close()
