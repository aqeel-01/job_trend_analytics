"""LangGraph state-machine for the V1 Monitor Agent."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TypedDict

from langgraph.graph import END, StateGraph

from pipeline.agents.monitor.tools import (
    check_database_health,
    check_fastapi_health,
    check_pipeline_status,
)
from pipeline.storage.database import Database

logger = logging.getLogger(__name__)


class MonitorStateDict(TypedDict, total=False):
    """LangGraph state schema for the monitor workflow."""

    status: str
    db_healthy: bool | None
    pipeline_fresh: bool | None
    api_healthy: bool | None
    new_data_exists: bool | None
    ingestion_failure: bool | None
    pipeline_check_error: bool | None
    last_run_at: str | None
    job_count: int
    skill_link_count: int
    freshness_threshold_hours: float
    tool_results: list[dict]
    error: str | None
    should_trigger_analysis: bool
    api_base_url: str


def evaluate_node(state: MonitorStateDict) -> MonitorStateDict:
    """Decide overall status and whether to trigger analysis."""
    db_ok = state.get("db_healthy", False)
    fresh = state.get("pipeline_fresh", False)
    failure = state.get("ingestion_failure", False)
    check_error = state.get("pipeline_check_error", False)
    api_ok = state.get("api_healthy", False)
    new_data = state.get("new_data_exists", False)

    if not db_ok:
        return {"status": "error", "error": "database unhealthy", "should_trigger_analysis": False}
    if check_error:
        return {
            "status": "error",
            "error": "pipeline status check failed",
            "should_trigger_analysis": False,
        }
    if failure:
        return {"status": "failure_detected", "error": "ingestion failure detected", "should_trigger_analysis": False}
    if not fresh:
        return {"status": "stale", "should_trigger_analysis": False}
    if not api_ok:
        return {
            "status": "error",
            "error": "FastAPI model-serving layer is not healthy",
            "should_trigger_analysis": False,
        }

    should_trigger = new_data
    status = "analysis_triggered" if should_trigger else "healthy"
    return {"status": status, "should_trigger_analysis": should_trigger}


def _after_db_check(state: MonitorStateDict) -> str:
    if state.get("db_healthy"):
        return "check_pipeline"
    return "evaluate"


def build_monitor_graph(database: Database) -> StateGraph:
    """Construct the LangGraph monitor workflow.

    The database instance is captured via closures in the node functions.
    """

    def check_db_node(state: MonitorStateDict) -> MonitorStateDict:
        result = check_database_health(database)
        tool_results = list(state.get("tool_results", []))
        tool_results.append({
            "tool": "check_database_health",
            "success": result["healthy"],
            "detail": result["detail"],
            "checked_at": datetime.now().isoformat(),
        })
        return {
            "status": "checking",
            "db_healthy": result["healthy"],
            "tool_results": tool_results,
        }

    def check_pipeline_node(state: MonitorStateDict) -> MonitorStateDict:
        threshold = state.get("freshness_threshold_hours", 168.0)
        result = check_pipeline_status(database, freshness_threshold_hours=threshold)
        tool_results = list(state.get("tool_results", []))
        check_error = bool(result.get("check_error"))
        tool_results.append({
            "tool": "check_pipeline_status",
            "success": (not check_error) and result["fresh"] and not result["ingestion_failure"],
            "detail": result["detail"],
            "checked_at": datetime.now().isoformat(),
        })
        return {
            "pipeline_fresh": result["fresh"],
            "new_data_exists": result["new_data_exists"],
            "ingestion_failure": result["ingestion_failure"],
            "pipeline_check_error": check_error,
            "last_run_at": result["last_run_at"],
            "job_count": result["job_count"],
            "skill_link_count": result["skill_link_count"],
            "tool_results": tool_results,
        }

    def check_api_node(state: MonitorStateDict) -> MonitorStateDict:
        base_url = state.get("api_base_url", "http://127.0.0.1:8000")
        result = check_fastapi_health(base_url=base_url)
        tool_results = list(state.get("tool_results", []))
        tool_results.append({
            "tool": "check_fastapi_health",
            "success": result["healthy"],
            "detail": result["detail"],
            "checked_at": datetime.now().isoformat(),
        })
        return {
            "api_healthy": result["healthy"],
            "tool_results": tool_results,
        }

    graph = StateGraph(MonitorStateDict)

    graph.add_node("check_db", check_db_node)
    graph.add_node("check_pipeline", check_pipeline_node)
    graph.add_node("check_api", check_api_node)
    graph.add_node("evaluate", evaluate_node)

    graph.set_entry_point("check_db")

    graph.add_conditional_edges("check_db", _after_db_check, {
        "check_pipeline": "check_pipeline",
        "evaluate": "evaluate",
    })
    graph.add_edge("check_pipeline", "check_api")
    graph.add_edge("check_api", "evaluate")
    graph.add_edge("evaluate", END)

    return graph


def run_monitor(
    database: Database,
    freshness_threshold_hours: float = 168.0,
    api_base_url: str = "http://127.0.0.1:8000",
) -> dict:
    """Build, compile, and invoke the monitor workflow, returning final state."""
    graph = build_monitor_graph(database)
    compiled = graph.compile()

    initial_state: MonitorStateDict = {
        "status": "pending",
        "db_healthy": None,
        "pipeline_fresh": None,
        "api_healthy": None,
        "new_data_exists": None,
        "ingestion_failure": None,
        "pipeline_check_error": None,
        "last_run_at": None,
        "job_count": 0,
        "skill_link_count": 0,
        "freshness_threshold_hours": freshness_threshold_hours,
        "tool_results": [],
        "error": None,
        "should_trigger_analysis": False,
        "api_base_url": api_base_url,
    }

    return compiled.invoke(initial_state)
