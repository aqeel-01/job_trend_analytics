"""LangGraph state-machine for the V1 Analyst Agent."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, StateGraph

from pipeline.agents.analyst.models import (
    AnalysisReport,
    MovementDirection,
    SignalStrength,
    SkillMovement,
)
from pipeline.agents.analyst.tools import (
    classify_signal_strength,
    fetch_model_info,
    fetch_trending_skills,
    interpret_direction,
)

logger = logging.getLogger(__name__)


class AnalystStateDict(TypedDict, total=False):
    """LangGraph state schema for the analyst workflow."""

    status: str
    api_base_url: str
    trending_limit: int

    # raw API responses
    trending_data: dict | None
    model_info_data: dict | None

    # interpreted output
    report: dict | None

    tool_results: list[dict]
    error: str | None


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------


def _make_tool_entry(tool: str, success: bool, detail: str) -> dict:
    return {
        "tool": tool,
        "success": success,
        "detail": detail,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def build_analyst_graph(
    api_base_url: str = "http://127.0.0.1:8000",
) -> StateGraph:
    """Construct the LangGraph analyst workflow."""

    def fetch_trends_node(state: AnalystStateDict) -> AnalystStateDict:
        url = state.get("api_base_url", api_base_url)
        limit = state.get("trending_limit", 200)
        result = fetch_trending_skills(base_url=url, limit=limit)
        tool_results = list(state.get("tool_results", []))
        tool_results.append(_make_tool_entry(
            "fetch_trending_skills", result["success"], result["detail"],
        ))
        if not result["success"]:
            return {
                "status": "error",
                "trending_data": None,
                "tool_results": tool_results,
                "error": result["detail"],
            }
        return {
            "status": "fetched_trends",
            "trending_data": result["data"],
            "tool_results": tool_results,
        }

    def fetch_model_info_node(state: AnalystStateDict) -> AnalystStateDict:
        url = state.get("api_base_url", api_base_url)
        result = fetch_model_info(base_url=url)
        tool_results = list(state.get("tool_results", []))
        tool_results.append(_make_tool_entry(
            "fetch_model_info", result["success"], result["detail"],
        ))
        return {
            "model_info_data": result["data"],
            "tool_results": tool_results,
        }

    def interpret_node(state: AnalystStateDict) -> AnalystStateDict:
        trending = state.get("trending_data")
        if trending is None:
            return {"status": "error", "error": "no trending data to interpret"}

        skills_raw: list[dict] = trending.get("skills", [])
        model_version = trending.get("model_version", "unknown")
        generated_at_str = trending.get("generated_at", datetime.now(timezone.utc).isoformat())
        period_count = trending.get("period_count", 0)

        try:
            generated_at = datetime.fromisoformat(generated_at_str)
        except (ValueError, TypeError):
            generated_at = datetime.now(timezone.utc)

        movements: list[SkillMovement] = []
        for s in skills_raw:
            direction = interpret_direction(s.get("direction", "unknown"))
            strength = classify_signal_strength(
                s.get("z_score"),
                s.get("change_percent"),
                s.get("trend", ""),
            )
            movements.append(SkillMovement(
                skill=s["skill"],
                direction=MovementDirection(direction),
                signal_strength=SignalStrength(strength),
                current_mentions=s.get("current_mentions", 0),
                previous_mentions=s.get("previous_mentions", 0),
                change=s.get("change", 0),
                change_percent=s.get("change_percent"),
                z_score=s.get("z_score"),
                raw_trend=s.get("trend", ""),
                raw_direction=s.get("direction", ""),
            ))

        strong = [m for m in movements if m.signal_strength == SignalStrength.STRONG]
        weak = [m for m in movements if m.signal_strength == SignalStrength.WEAK]

        def _sort_key(m: SkillMovement) -> tuple:
            z = abs(m.z_score) if m.z_score is not None else -1.0
            cp = abs(m.change_percent) if m.change_percent is not None else -1.0
            return (-z, -cp)

        risers = sorted(
            [m for m in movements if m.direction == MovementDirection.RISING],
            key=_sort_key,
        )
        fallers = sorted(
            [m for m in movements if m.direction == MovementDirection.FALLING],
            key=_sort_key,
        )
        stable_skills = [
            m.skill for m in movements if m.direction == MovementDirection.STABLE
        ]

        notes: list[str] = []
        if period_count < 3:
            notes.append(
                f"Only {period_count} period(s) of data available; "
                f"z-scores require ≥3 periods for meaningful results."
            )
        insufficient = [m for m in movements if m.raw_trend == "insufficient_data"]
        if insufficient:
            notes.append(
                f"{len(insufficient)} of {len(movements)} skills lack sufficient "
                f"history for z-score computation."
            )
        unknown_dir = [m for m in movements if m.direction == MovementDirection.UNKNOWN]
        if unknown_dir:
            notes.append(
                f"{len(unknown_dir)} skill(s) have unknown direction due to "
                f"insufficient historical data."
            )

        analyzed_at = datetime.now(timezone.utc)
        report = AnalysisReport(
            model_version=model_version,
            generated_at=generated_at,
            analyzed_at=analyzed_at,
            period_count=period_count,
            total_skills_in_model=len(movements),
            strong_signals=strong,
            weak_signals=weak,
            top_risers=risers,
            top_fallers=fallers,
            stable_skills=stable_skills,
            data_quality_notes=notes,
        )

        return {
            "status": "completed",
            "report": report.to_dict(),
        }

    def _after_fetch_trends(state: AnalystStateDict) -> str:
        if state.get("trending_data") is None:
            return "end"
        return "fetch_model_info"

    graph = StateGraph(AnalystStateDict)

    graph.add_node("fetch_trends", fetch_trends_node)
    graph.add_node("fetch_model_info", fetch_model_info_node)
    graph.add_node("interpret", interpret_node)

    graph.set_entry_point("fetch_trends")

    graph.add_conditional_edges("fetch_trends", _after_fetch_trends, {
        "fetch_model_info": "fetch_model_info",
        "end": END,
    })
    graph.add_edge("fetch_model_info", "interpret")
    graph.add_edge("interpret", END)

    return graph


def run_analyst(
    api_base_url: str = "http://127.0.0.1:8000",
    trending_limit: int = 200,
) -> dict:
    """Build, compile, and invoke the analyst workflow, returning final state."""
    graph = build_analyst_graph(api_base_url=api_base_url)
    compiled = graph.compile()

    initial_state: AnalystStateDict = {
        "status": "pending",
        "api_base_url": api_base_url,
        "trending_limit": trending_limit,
        "trending_data": None,
        "model_info_data": None,
        "report": None,
        "tool_results": [],
        "error": None,
    }

    return compiled.invoke(initial_state)
