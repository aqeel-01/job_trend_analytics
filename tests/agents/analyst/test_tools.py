"""Tests for Analyst Agent tool functions."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from pipeline.agents.analyst.tools import (
    classify_signal_strength,
    fetch_model_info,
    fetch_trending_skills,
    interpret_direction,
)


# -- fetch_trending_skills ----------------------------------------------------


class TestFetchTrendingSkills:
    def test_success(self):
        body = {
            "model_version": "v1.0",
            "generated_at": "2026-08-19T12:00:00Z",
            "period_count": 4,
            "limit": 200,
            "total_skills": 2,
            "skills": [{"skill": "Python"}],
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = body
        with patch("pipeline.agents.analyst.tools.httpx.get", return_value=mock_resp) as mock_get:
            result = fetch_trending_skills(base_url="http://test:8000", limit=50)
            mock_get.assert_called_once()
            call_kwargs = mock_get.call_args
            assert call_kwargs.kwargs["params"]["limit"] == 50
        assert result["success"] is True
        assert result["data"]["skills"][0]["skill"] == "Python"

    def test_api_down(self):
        with patch("pipeline.agents.analyst.tools.httpx.get", side_effect=httpx.ConnectError("")):
            result = fetch_trending_skills()
        assert result["success"] is False
        assert "connection refused" in result["detail"]

    def test_http_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        with patch("pipeline.agents.analyst.tools.httpx.get", return_value=mock_resp):
            result = fetch_trending_skills()
        assert result["success"] is False
        assert "500" in result["detail"]


class TestFetchModelInfo:
    def test_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"model_version": "v1.0", "method": "z_score"}
        with patch("pipeline.agents.analyst.tools.httpx.get", return_value=mock_resp):
            result = fetch_model_info()
        assert result["success"] is True
        assert result["data"]["method"] == "z_score"


# -- interpret helpers --------------------------------------------------------


class TestClassifySignalStrength:
    def test_strong_z_score(self):
        assert classify_signal_strength(z_score=1.5, change_percent=50.0, trend="rising") == "strong"

    def test_strong_change_percent(self):
        assert classify_signal_strength(z_score=0.3, change_percent=150.0, trend="rising") == "strong"

    def test_weak_signal(self):
        assert classify_signal_strength(z_score=0.2, change_percent=15.0, trend="stable") == "weak"

    def test_insufficient_data_strong_change(self):
        assert classify_signal_strength(z_score=None, change_percent=200.0, trend="insufficient_data") == "strong"

    def test_insufficient_data_small_change(self):
        assert classify_signal_strength(z_score=None, change_percent=10.0, trend="insufficient_data") == "weak"

    def test_no_z_no_change(self):
        assert classify_signal_strength(z_score=None, change_percent=None, trend="insufficient_data") == "weak"


class TestInterpretDirection:
    def test_up(self):
        assert interpret_direction("up") == "rising"

    def test_down(self):
        assert interpret_direction("down") == "falling"

    def test_flat(self):
        assert interpret_direction("flat") == "stable"

    def test_unknown(self):
        assert interpret_direction("unknown") == "unknown"

    def test_garbage(self):
        assert interpret_direction("xyz") == "unknown"
