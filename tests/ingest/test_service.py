"""Tests for ingestion service orchestration."""

import json
from pathlib import Path

from pipeline.ingest.exceptions import APIRequestError
from pipeline.ingest.service import IngestionService


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


def _build_service(client, job_repository, pipeline_run_repository, database):
    return IngestionService(
        client=client,
        job_repository=job_repository,
        pipeline_run_repository=pipeline_run_repository,
        database=database,
    )


def test_ingestion_service_inserts_jobs(job_repository, pipeline_run_repository, database) -> None:
    page_one = _load_fixture("arbeitnow_page.json")
    client = MockJobBoardClient({1: page_one})
    service = _build_service(client, job_repository, pipeline_run_repository, database)

    result = service.run()

    assert result.status == "completed"
    assert result.pages_fetched == 1
    assert result.records_fetched == 2
    assert result.records_inserted == 2
    assert result.records_duplicates == 0
    assert result.records_failed == 0
    assert job_repository.count_jobs() == 2
    assert pipeline_run_repository.count_runs() == 1


def test_ingestion_service_skips_duplicates(job_repository, pipeline_run_repository, database) -> None:
    page_one = _load_fixture("arbeitnow_page.json")
    client = MockJobBoardClient({1: page_one})
    service = _build_service(client, job_repository, pipeline_run_repository, database)

    first = service.run()
    second = service.run()

    assert first.records_inserted == 2
    assert second.records_inserted == 0
    assert second.records_duplicates == 2
    assert job_repository.count_jobs() == 2


def test_ingestion_service_paginates(job_repository, pipeline_run_repository, database) -> None:
    page_one = _load_fixture("arbeitnow_page.json")
    page_two = _load_fixture("arbeitnow_page_2.json")
    page_one["links"]["next"] = "https://www.arbeitnow.com/api/job-board-api?page=2"

    client = MockJobBoardClient({1: page_one, 2: page_two})
    service = _build_service(client, job_repository, pipeline_run_repository, database)

    result = service.run()

    assert result.pages_fetched == 2
    assert result.records_inserted == 3
    assert client.calls == [1, 2]


def test_ingestion_service_handles_api_failure(
    job_repository, pipeline_run_repository, database
) -> None:
    page_one = _load_fixture("arbeitnow_page.json")
    client = MockJobBoardClient({1: page_one}, fail_page=1)
    service = _build_service(client, job_repository, pipeline_run_repository, database)

    result = service.run()

    assert result.status == "failed"
    assert result.pages_fetched == 0
    assert result.records_inserted == 0
    assert result.error_message is not None
    assert pipeline_run_repository.count_runs() == 1


def test_ingestion_service_max_pages_limit(
    job_repository, pipeline_run_repository, database
) -> None:
    page_one = _load_fixture("arbeitnow_page.json")
    page_two = _load_fixture("arbeitnow_page_2.json")
    page_one["links"]["next"] = "https://www.arbeitnow.com/api/job-board-api?page=2"

    client = MockJobBoardClient({1: page_one, 2: page_two})
    service = _build_service(client, job_repository, pipeline_run_repository, database)

    result = service.run(max_pages=1)

    assert result.pages_fetched == 1
    assert result.records_inserted == 2
    assert client.calls == [1]


def test_ingestion_service_normalization_failure(
    job_repository, pipeline_run_repository, database
) -> None:
    payload = {
        "data": [
            {"slug": "bad", "company_name": "Co"},
            _load_fixture("arbeitnow_page.json")["data"][0],
        ],
        "links": {"next": None},
    }
    client = MockJobBoardClient({1: payload})
    service = _build_service(client, job_repository, pipeline_run_repository, database)

    result = service.run()

    assert result.records_fetched == 2
    assert result.records_failed == 1
    assert result.records_inserted == 1
    assert result.status == "completed"
