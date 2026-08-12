"""Tests for the Arbeitnow API client."""

from unittest.mock import MagicMock

import httpx
import pytest

from pipeline.ingest.client import ArbeitnowClient
from pipeline.ingest.exceptions import APIRequestError


def test_fetch_page_success() -> None:
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [], "links": {"next": None}}
    mock_client.get.return_value = mock_response

    client = ArbeitnowClient(
        base_url="https://www.arbeitnow.com/api/job-board-api",
        max_retries=1,
        client=mock_client,
    )

    payload = client.fetch_page(1)

    mock_client.get.assert_called_once_with(
        "https://www.arbeitnow.com/api/job-board-api?page=1"
    )
    assert payload["data"] == []


def test_fetch_page_retries_then_raises() -> None:
    mock_client = MagicMock()
    mock_client.get.side_effect = httpx.ConnectError("connection failed")

    client = ArbeitnowClient(
        base_url="https://www.arbeitnow.com/api/job-board-api",
        max_retries=2,
        client=mock_client,
    )

    with pytest.raises(APIRequestError, match="page 1"):
        client.fetch_page(1)

    assert mock_client.get.call_count == 2


def test_fetch_page_http_error() -> None:
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "error",
        request=MagicMock(),
        response=MagicMock(status_code=500),
    )
    mock_client.get.return_value = mock_response

    client = ArbeitnowClient(
        base_url="https://www.arbeitnow.com/api/job-board-api",
        max_retries=1,
        client=mock_client,
    )

    with pytest.raises(APIRequestError):
        client.fetch_page(3)
