"""Tests for Report Writer LangGraph workflow."""

from unittest.mock import patch

import pytest

from pipeline.agents.report_writer.graph import (
    ReportWriterStateDict,
    build_report_writer_graph,
    run_report_writer,
    _parse_markdown_sections,
)


MOCK_LLM_RESPONSE = """\
## Executive Summary

Python demand surged by 100.0% (40→80 mentions, z-score 9.00) while Java declined by -40.0% (50→30 mentions, z-score -3.00).

## Rising Skills

- **Python**: Mentions increased from 40 to 80 (+100.0%), with a z-score of 9.00, indicating strong upward momentum.

## Declining Skills

- **Java**: Mentions dropped from 50 to 30 (-40.0%), with a z-score of -3.00, indicating a notable decline.

## Stable Skills

Go showed no significant movement this period.

## Weak Signals

Rust saw a large increase (+400.0%) but lacks sufficient historical data for a reliable z-score assessment.

## Methodology Note

Analysis based on model v1.0 using z-score statistical trending across 4 periods."""


def _mock_ollama_success(*args, **kwargs):
    return {"success": True, "text": MOCK_LLM_RESPONSE, "model": "llama3", "detail": "ok"}


def _mock_ollama_failure(*args, **kwargs):
    return {"success": False, "text": "", "model": "llama3", "detail": "connection refused"}


# -- Valid analyst input -------------------------------------------------------


class TestValidAnalystInput:
    @patch("pipeline.agents.report_writer.graph.generate_with_ollama", side_effect=_mock_ollama_success)
    def test_completed_report(self, mock_llm, valid_analyst_report):
        result = run_report_writer(valid_analyst_report)
        assert result["status"] == "completed"
        assert result["report"] is not None

    @patch("pipeline.agents.report_writer.graph.generate_with_ollama", side_effect=_mock_ollama_success)
    def test_report_has_sections(self, mock_llm, valid_analyst_report):
        result = run_report_writer(valid_analyst_report)
        report = result["report"]
        assert len(report["sections"]) > 0
        headings = [s["heading"] for s in report["sections"]]
        assert any("Rising" in h or "Executive" in h for h in headings)

    @patch("pipeline.agents.report_writer.graph.generate_with_ollama", side_effect=_mock_ollama_success)
    def test_report_preserves_model_version(self, mock_llm, valid_analyst_report):
        result = run_report_writer(valid_analyst_report)
        assert result["report"]["model_version"] == "v1.0"

    @patch("pipeline.agents.report_writer.graph.generate_with_ollama", side_effect=_mock_ollama_success)
    def test_report_includes_limitations(self, mock_llm, valid_analyst_report):
        result = run_report_writer(valid_analyst_report)
        assert len(result["report"]["limitations"]) > 0

    @patch("pipeline.agents.report_writer.graph.generate_with_ollama", side_effect=_mock_ollama_success)
    def test_markdown_output_contains_skills(self, mock_llm, valid_analyst_report):
        result = run_report_writer(valid_analyst_report)
        md = result["report_markdown"]
        assert "Python" in md
        assert "Java" in md

    @patch("pipeline.agents.report_writer.graph.generate_with_ollama", side_effect=_mock_ollama_success)
    def test_tool_results_recorded(self, mock_llm, valid_analyst_report):
        result = run_report_writer(valid_analyst_report)
        tools = [t["tool"] for t in result["tool_results"]]
        assert "validate_analyst_report" in tools
        assert "generate_with_ollama" in tools

    @patch("pipeline.agents.report_writer.graph.generate_with_ollama", side_effect=_mock_ollama_success)
    def test_llm_model_name_recorded(self, mock_llm, valid_analyst_report):
        result = run_report_writer(valid_analyst_report)
        assert result["report"]["llm_model_used"] == "llama3"


# -- Missing / insufficient evidence ------------------------------------------


class TestMissingEvidence:
    def test_none_report_rejected(self):
        result = run_report_writer(None)
        assert result["status"] == "invalid_input"
        assert result["report"] is None
        assert "None" in result.get("error", "")

    def test_empty_signals_rejected(self):
        report = {
            "model_version": "v1",
            "total_skills_in_model": 0,
            "strong_signals": [],
            "weak_signals": [],
            "period_count": 0,
        }
        result = run_report_writer(report)
        assert result["status"] == "invalid_input"

    def test_missing_keys_rejected(self):
        result = run_report_writer({"model_version": "v1"})
        assert result["status"] == "invalid_input"
        assert result["error"] is not None


# -- LLM fallback when Ollama unavailable ------------------------------------


class TestLlmFallback:
    @patch("pipeline.agents.report_writer.graph.generate_with_ollama", side_effect=_mock_ollama_failure)
    def test_fallback_produces_report(self, mock_llm, valid_analyst_report):
        result = run_report_writer(valid_analyst_report)
        assert result["status"] == "completed"
        assert result["report"] is not None

    @patch("pipeline.agents.report_writer.graph.generate_with_ollama", side_effect=_mock_ollama_failure)
    def test_fallback_report_notes_llm_unavailable(self, mock_llm, valid_analyst_report):
        result = run_report_writer(valid_analyst_report)
        report = result["report"]
        assert report["llm_model_used"] == "fallback (no LLM)"
        assert any("LLM" in l or "fallback" in l for l in report["limitations"])

    @patch("pipeline.agents.report_writer.graph.generate_with_ollama", side_effect=_mock_ollama_failure)
    def test_fallback_markdown_still_contains_data(self, mock_llm, valid_analyst_report):
        result = run_report_writer(valid_analyst_report)
        md = result["report_markdown"]
        assert "Python" in md
        assert "80" in md


# -- Malformed model output ---------------------------------------------------


class TestMalformedOutput:
    @patch("pipeline.agents.report_writer.graph.generate_with_ollama")
    def test_llm_returns_empty_string(self, mock_llm, valid_analyst_report):
        mock_llm.return_value = {"success": True, "text": "", "model": "llama3", "detail": "ok"}
        result = run_report_writer(valid_analyst_report)
        assert result["status"] == "completed"
        assert result["report"] is not None

    @patch("pipeline.agents.report_writer.graph.generate_with_ollama")
    def test_llm_returns_no_headings(self, mock_llm, valid_analyst_report):
        mock_llm.return_value = {
            "success": True,
            "text": "Just a plain text paragraph with no markdown headings.",
            "model": "llama3",
            "detail": "ok",
        }
        result = run_report_writer(valid_analyst_report)
        assert result["status"] == "completed"
        sections = result["report"]["sections"]
        assert len(sections) >= 1

    @patch("pipeline.agents.report_writer.graph.generate_with_ollama")
    def test_llm_returns_partial_markdown(self, mock_llm, valid_analyst_report):
        mock_llm.return_value = {
            "success": True,
            "text": "## Summary\nSome content\n## Details\nMore content",
            "model": "llama3",
            "detail": "ok",
        }
        result = run_report_writer(valid_analyst_report)
        assert result["status"] == "completed"
        headings = [s["heading"] for s in result["report"]["sections"]]
        assert "Summary" in headings
        assert "Details" in headings


# -- Report structure ---------------------------------------------------------


class TestReportStructure:
    @patch("pipeline.agents.report_writer.graph.generate_with_ollama", side_effect=_mock_ollama_success)
    def test_report_dict_has_required_keys(self, mock_llm, valid_analyst_report):
        result = run_report_writer(valid_analyst_report)
        report = result["report"]
        for key in ["title", "generated_at", "model_version", "period_count",
                     "total_skills_analyzed", "sections", "limitations", "llm_model_used"]:
            assert key in report, f"missing key: {key}"

    @patch("pipeline.agents.report_writer.graph.generate_with_ollama", side_effect=_mock_ollama_success)
    def test_each_section_has_heading_and_body(self, mock_llm, valid_analyst_report):
        result = run_report_writer(valid_analyst_report)
        for section in result["report"]["sections"]:
            assert "heading" in section
            assert "body" in section

    @patch("pipeline.agents.report_writer.graph.generate_with_ollama", side_effect=_mock_ollama_success)
    def test_markdown_starts_with_title(self, mock_llm, valid_analyst_report):
        result = run_report_writer(valid_analyst_report)
        md = result["report_markdown"]
        assert md.startswith("# Weekly Job-Market")


class TestParseMarkdownSections:
    def test_parses_headings(self):
        md = "## Foo\nContent A\n## Bar\nContent B"
        sections = _parse_markdown_sections(md)
        assert len(sections) == 2
        assert sections[0].heading == "Foo"
        assert sections[1].heading == "Bar"

    def test_empty_input(self):
        assert _parse_markdown_sections("") == []

    def test_no_headings(self):
        sections = _parse_markdown_sections("Just text no headings")
        assert len(sections) == 1
        assert sections[0].heading == "Report"


class TestGraphStructure:
    def test_graph_compiles(self):
        graph = build_report_writer_graph()
        compiled = graph.compile()
        assert compiled is not None

    def test_graph_has_expected_nodes(self):
        graph = build_report_writer_graph()
        node_names = set(graph.nodes.keys())
        assert "validate_input" in node_names
        assert "generate_report" in node_names
        assert "structure_report" in node_names
