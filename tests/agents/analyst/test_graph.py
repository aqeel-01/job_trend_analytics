"""Tests for the Analyst Agent LangGraph workflow.

Every test verifies that the Analyst consumes ML API responses (mocked)
rather than bypassing the API.
"""

from unittest.mock import MagicMock, patch

import pytest

from pipeline.agents.analyst.graph import (
    AnalystStateDict,
    build_analyst_graph,
    run_analyst,
)


MOCK_TRENDING_RESPONSE = {
    "model_version": "v1.0",
    "generated_at": "2026-08-19T12:00:00Z",
    "period_count": 4,
    "limit": 200,
    "total_skills": 5,
    "skills": [
        {
            "skill": "Python",
            "current_mentions": 80,
            "previous_mentions": 40,
            "change": 40,
            "change_percent": 100.0,
            "historical_mean": 35.0,
            "historical_std": 5.0,
            "z_score": 9.0,
            "trend": "rising",
            "direction": "up",
        },
        {
            "skill": "Java",
            "current_mentions": 30,
            "previous_mentions": 50,
            "change": -20,
            "change_percent": -40.0,
            "historical_mean": 45.0,
            "historical_std": 5.0,
            "z_score": -3.0,
            "trend": "falling",
            "direction": "down",
        },
        {
            "skill": "Go",
            "current_mentions": 20,
            "previous_mentions": 19,
            "change": 1,
            "change_percent": 5.26,
            "historical_mean": 19.0,
            "historical_std": 2.0,
            "z_score": 0.5,
            "trend": "stable",
            "direction": "flat",
        },
        {
            "skill": "Rust",
            "current_mentions": 15,
            "previous_mentions": 3,
            "change": 12,
            "change_percent": 400.0,
            "historical_mean": 3.0,
            "historical_std": None,
            "z_score": None,
            "trend": "insufficient_data",
            "direction": "unknown",
        },
        {
            "skill": "COBOL",
            "current_mentions": 2,
            "previous_mentions": 1,
            "change": 1,
            "change_percent": 100.0,
            "historical_mean": 1.0,
            "historical_std": None,
            "z_score": None,
            "trend": "insufficient_data",
            "direction": "unknown",
        },
    ],
}

MOCK_MODEL_INFO = {
    "model_version": "v1.0",
    "method": "z_score",
    "min_history_periods": 2,
    "z_rising_threshold": 0.5,
    "z_falling_threshold": -0.5,
}


def _mock_trending_success(*args, **kwargs):
    return {"success": True, "data": MOCK_TRENDING_RESPONSE, "detail": "ok"}


def _mock_model_info_success(*args, **kwargs):
    return {"success": True, "data": MOCK_MODEL_INFO, "detail": "ok"}


def _mock_trending_failure(*args, **kwargs):
    return {"success": False, "data": None, "detail": "connection refused"}


class TestRunAnalyst:
    """Full workflow tests — all verify that the analyst calls the ML API."""

    @patch("pipeline.agents.analyst.graph.fetch_model_info", side_effect=_mock_model_info_success)
    @patch("pipeline.agents.analyst.graph.fetch_trending_skills", side_effect=_mock_trending_success)
    def test_successful_analysis(self, mock_trends, mock_info):
        result = run_analyst(api_base_url="http://test:8000")

        mock_trends.assert_called_once()
        assert result["status"] == "completed"
        assert result["report"] is not None

        report = result["report"]
        assert report["model_version"] == "v1.0"
        assert report["total_skills_in_model"] == 5

    @patch("pipeline.agents.analyst.graph.fetch_model_info", side_effect=_mock_model_info_success)
    @patch("pipeline.agents.analyst.graph.fetch_trending_skills", side_effect=_mock_trending_success)
    def test_api_data_flows_into_report(self, mock_trends, mock_info):
        """Verify the report content comes from the API, not invented."""
        result = run_analyst()
        report = result["report"]

        skill_names = {s["skill"] for s in report["strong_signals"] + report["weak_signals"]}
        api_skill_names = {s["skill"] for s in MOCK_TRENDING_RESPONSE["skills"]}
        assert skill_names == api_skill_names

    @patch("pipeline.agents.analyst.graph.fetch_model_info", side_effect=_mock_model_info_success)
    @patch("pipeline.agents.analyst.graph.fetch_trending_skills", side_effect=_mock_trending_success)
    def test_strong_vs_weak_signals(self, mock_trends, mock_info):
        result = run_analyst()
        report = result["report"]

        strong_names = {s["skill"] for s in report["strong_signals"]}
        weak_names = {s["skill"] for s in report["weak_signals"]}

        assert "Python" in strong_names   # z=9.0
        assert "Java" in strong_names     # z=-3.0
        assert "Rust" in strong_names     # 400% change despite insufficient_data
        assert "Go" in weak_names         # z=0.5, 5% change

    @patch("pipeline.agents.analyst.graph.fetch_model_info", side_effect=_mock_model_info_success)
    @patch("pipeline.agents.analyst.graph.fetch_trending_skills", side_effect=_mock_trending_success)
    def test_risers_and_fallers(self, mock_trends, mock_info):
        result = run_analyst()
        report = result["report"]

        riser_names = [s["skill"] for s in report["top_risers"]]
        faller_names = [s["skill"] for s in report["top_fallers"]]

        assert "Python" in riser_names
        assert "Java" in faller_names
        assert "Go" not in riser_names
        assert "Go" not in faller_names

    @patch("pipeline.agents.analyst.graph.fetch_model_info", side_effect=_mock_model_info_success)
    @patch("pipeline.agents.analyst.graph.fetch_trending_skills", side_effect=_mock_trending_success)
    def test_stable_skills_identified(self, mock_trends, mock_info):
        result = run_analyst()
        assert "Go" in result["report"]["stable_skills"]

    @patch("pipeline.agents.analyst.graph.fetch_model_info", side_effect=_mock_model_info_success)
    @patch("pipeline.agents.analyst.graph.fetch_trending_skills", side_effect=_mock_trending_success)
    def test_data_quality_notes(self, mock_trends, mock_info):
        result = run_analyst()
        notes = result["report"]["data_quality_notes"]
        assert any("insufficient" in n.lower() for n in notes)

    @patch("pipeline.agents.analyst.graph.fetch_trending_skills", side_effect=_mock_trending_failure)
    def test_api_failure_produces_error(self, mock_trends):
        result = run_analyst()
        assert result["status"] == "error"
        assert result["report"] is None
        mock_trends.assert_called_once()

    @patch("pipeline.agents.analyst.graph.fetch_model_info", side_effect=_mock_model_info_success)
    @patch("pipeline.agents.analyst.graph.fetch_trending_skills", side_effect=_mock_trending_success)
    def test_tool_results_recorded(self, mock_trends, mock_info):
        result = run_analyst()
        tools_called = [t["tool"] for t in result["tool_results"]]
        assert "fetch_trending_skills" in tools_called
        assert "fetch_model_info" in tools_called

    @patch("pipeline.agents.analyst.graph.fetch_model_info", side_effect=_mock_model_info_success)
    @patch("pipeline.agents.analyst.graph.fetch_trending_skills", side_effect=_mock_trending_success)
    def test_report_preserves_api_values(self, mock_trends, mock_info):
        """The report's skill data must match API response values exactly."""
        result = run_analyst()
        report = result["report"]
        all_skills = report["strong_signals"] + report["weak_signals"]
        python_entry = next(s for s in all_skills if s["skill"] == "Python")

        assert python_entry["current_mentions"] == 80
        assert python_entry["previous_mentions"] == 40
        assert python_entry["z_score"] == 9.0
        assert python_entry["change_percent"] == 100.0
        assert python_entry["raw_direction"] == "up"


class TestGraphStructure:
    def test_graph_compiles(self):
        graph = build_analyst_graph()
        compiled = graph.compile()
        assert compiled is not None

    def test_graph_has_expected_nodes(self):
        graph = build_analyst_graph()
        node_names = set(graph.nodes.keys())
        assert "fetch_trends" in node_names
        assert "fetch_model_info" in node_names
        assert "interpret" in node_names
