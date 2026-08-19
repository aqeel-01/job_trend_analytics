"""LangGraph state-machine for the V1 Report Writer Agent."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, StateGraph

from pipeline.agents.report_writer.models import ReportSection, WeeklyReport
from pipeline.agents.report_writer.prompt import SYSTEM_PROMPT, build_report_prompt
from pipeline.agents.report_writer.tools import (
    build_fallback_report_text,
    generate_with_ollama,
    validate_analyst_report,
)

logger = logging.getLogger(__name__)


class ReportWriterStateDict(TypedDict, total=False):
    """LangGraph state schema for the report-writer workflow."""

    status: str
    analyst_report: dict | None
    validation_issues: list[str]
    llm_response: str
    report: dict | None
    report_markdown: str
    tool_results: list[dict]
    error: str | None
    ollama_model: str
    ollama_base_url: str
    ollama_timeout: float


def _tool_entry(tool: str, success: bool, detail: str) -> dict:
    return {
        "tool": tool,
        "success": success,
        "detail": detail,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def build_report_writer_graph(
    ollama_model: str = "llama3",
    ollama_base_url: str = "http://localhost:11434",
    ollama_timeout: float = 120.0,
) -> StateGraph:
    """Construct the LangGraph report-writer workflow."""

    def validate_input_node(state: ReportWriterStateDict) -> ReportWriterStateDict:
        report = state.get("analyst_report")
        result = validate_analyst_report(report)
        tool_results = list(state.get("tool_results", []))
        tool_results.append(_tool_entry(
            "validate_analyst_report", result["valid"],
            f"issues={result['issues']}" if result["issues"] else "ok",
        ))
        if not result["valid"]:
            return {
                "status": "invalid_input",
                "validation_issues": result["issues"],
                "tool_results": tool_results,
                "error": "; ".join(result["issues"]),
            }
        return {
            "status": "validated",
            "validation_issues": [],
            "tool_results": tool_results,
        }

    def generate_report_node(state: ReportWriterStateDict) -> ReportWriterStateDict:
        report_data = state.get("analyst_report", {})
        model = state.get("ollama_model", ollama_model)
        base_url = state.get("ollama_base_url", ollama_base_url)
        timeout = state.get("ollama_timeout", ollama_timeout)

        user_prompt = build_report_prompt(report_data)
        result = generate_with_ollama(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=model,
            base_url=base_url,
            timeout=timeout,
        )
        tool_results = list(state.get("tool_results", []))
        tool_results.append(_tool_entry(
            "generate_with_ollama", result["success"], result["detail"],
        ))

        if not result["success"]:
            fallback_text = build_fallback_report_text(
                report_data, [f"LLM unavailable: {result['detail']}"],
            )
            return {
                "status": "completed_fallback",
                "llm_response": "",
                "report_markdown": fallback_text,
                "tool_results": tool_results,
            }

        return {
            "status": "generated",
            "llm_response": result["text"],
            "tool_results": tool_results,
        }

    def structure_report_node(state: ReportWriterStateDict) -> ReportWriterStateDict:
        analyst = state.get("analyst_report", {})
        llm_text = state.get("llm_response", "")
        model_name = state.get("ollama_model", ollama_model)

        is_fallback = state.get("status") == "completed_fallback"
        raw_md = state.get("report_markdown", "") if is_fallback else llm_text

        sections = _parse_markdown_sections(raw_md)
        now = datetime.now(timezone.utc)

        limitations = list(analyst.get("data_quality_notes", []))
        if is_fallback:
            limitations.append("Report generated using deterministic fallback — LLM was unavailable.")

        report = WeeklyReport(
            title="Weekly Job-Market Skill-Demand Report",
            generated_at=now,
            model_version=analyst.get("model_version", "unknown"),
            period_count=analyst.get("period_count", 0),
            total_skills_analyzed=analyst.get("total_skills_in_model", 0),
            sections=sections,
            limitations=limitations,
            llm_model_used=model_name if not is_fallback else "fallback (no LLM)",
            raw_llm_response=llm_text,
        )

        return {
            "status": "completed",
            "report": report.to_dict(),
            "report_markdown": report.to_markdown(),
        }

    def _after_validate(state: ReportWriterStateDict) -> str:
        if state.get("status") == "invalid_input":
            return "end"
        return "generate_report"

    def _after_generate(state: ReportWriterStateDict) -> str:
        return "structure_report"

    graph = StateGraph(ReportWriterStateDict)

    graph.add_node("validate_input", validate_input_node)
    graph.add_node("generate_report", generate_report_node)
    graph.add_node("structure_report", structure_report_node)

    graph.set_entry_point("validate_input")

    graph.add_conditional_edges("validate_input", _after_validate, {
        "generate_report": "generate_report",
        "end": END,
    })
    graph.add_edge("generate_report", "structure_report")
    graph.add_edge("structure_report", END)

    return graph


def run_report_writer(
    analyst_report: dict,
    ollama_model: str = "llama3",
    ollama_base_url: str = "http://localhost:11434",
    ollama_timeout: float = 120.0,
) -> dict:
    """Build, compile, and invoke the report-writer workflow."""
    graph = build_report_writer_graph(
        ollama_model=ollama_model,
        ollama_base_url=ollama_base_url,
        ollama_timeout=ollama_timeout,
    )
    compiled = graph.compile()

    initial_state: ReportWriterStateDict = {
        "status": "pending",
        "analyst_report": analyst_report,
        "validation_issues": [],
        "llm_response": "",
        "report": None,
        "report_markdown": "",
        "tool_results": [],
        "error": None,
        "ollama_model": ollama_model,
        "ollama_base_url": ollama_base_url,
        "ollama_timeout": ollama_timeout,
    }

    return compiled.invoke(initial_state)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


def _parse_markdown_sections(md: str) -> list[ReportSection]:
    """Split markdown text into ReportSection objects by headings."""
    matches = list(_HEADING_RE.finditer(md))
    if not matches:
        if md.strip():
            return [ReportSection(heading="Report", body=md.strip())]
        return []

    sections: list[ReportSection] = []
    for i, match in enumerate(matches):
        heading = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        body = md[start:end].strip()
        if body or heading:
            sections.append(ReportSection(heading=heading, body=body))
    return sections
