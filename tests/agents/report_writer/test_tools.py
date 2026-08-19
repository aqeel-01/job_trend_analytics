"""Tests for Report Writer tools."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from pipeline.agents.report_writer.tools import (
    build_fallback_report_text,
    generate_with_ollama,
    validate_analyst_report,
)


# -- validate_analyst_report --------------------------------------------------


class TestValidateAnalystReport:
    def test_valid_report(self, valid_analyst_report):
        result = validate_analyst_report(valid_analyst_report)
        assert result["valid"] is True
        assert result["issues"] == []

    def test_none_report(self):
        result = validate_analyst_report(None)
        assert result["valid"] is False
        assert any("None" in i for i in result["issues"])

    def test_missing_required_fields(self):
        result = validate_analyst_report({"model_version": "v1"})
        assert result["valid"] is False
        assert any("total_skills_in_model" in i for i in result["issues"])

    def test_empty_signals(self):
        report = {
            "model_version": "v1",
            "total_skills_in_model": 0,
            "strong_signals": [],
            "weak_signals": [],
            "period_count": 1,
        }
        result = validate_analyst_report(report)
        assert result["valid"] is False
        assert any("no skill signals" in i for i in result["issues"])

    def test_zero_periods(self):
        report = {
            "model_version": "v1",
            "total_skills_in_model": 1,
            "strong_signals": [{"skill": "X"}],
            "weak_signals": [],
            "period_count": 0,
        }
        result = validate_analyst_report(report)
        assert result["valid"] is False
        assert any("period_count" in i for i in result["issues"])


# -- generate_with_ollama -----------------------------------------------------


class TestGenerateWithOllama:
    def test_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "# Report\nContent here"}
        with patch("pipeline.agents.report_writer.tools.httpx.post", return_value=mock_resp):
            result = generate_with_ollama("sys", "user")
        assert result["success"] is True
        assert "Report" in result["text"]

    def test_connection_refused(self):
        with patch("pipeline.agents.report_writer.tools.httpx.post",
                   side_effect=httpx.ConnectError("")):
            result = generate_with_ollama("sys", "user")
        assert result["success"] is False
        assert "connection refused" in result["detail"]

    def test_http_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "model not found"
        with patch("pipeline.agents.report_writer.tools.httpx.post", return_value=mock_resp):
            result = generate_with_ollama("sys", "user")
        assert result["success"] is False
        assert "500" in result["detail"]


# -- build_fallback_report_text -----------------------------------------------


class TestBuildFallbackReportText:
    def test_produces_markdown(self, valid_analyst_report):
        text = build_fallback_report_text(valid_analyst_report, [])
        assert "# Weekly Job-Market" in text
        assert "Python" in text
        assert "Java" in text

    def test_includes_limitations(self, valid_analyst_report):
        text = build_fallback_report_text(valid_analyst_report, ["LLM unavailable"])
        assert "LLM unavailable" in text

    def test_includes_stable_skills(self, valid_analyst_report):
        text = build_fallback_report_text(valid_analyst_report, [])
        assert "Go" in text

    def test_includes_weak_signals(self, valid_analyst_report):
        text = build_fallback_report_text(valid_analyst_report, [])
        assert "Rust" in text
