"""LangGraph orchestrator: Monitor → Analyst → Report Writer → record results."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph

from pipeline.agents.analyst.graph import run_analyst
from pipeline.agents.monitor.graph import run_monitor
from pipeline.agents.report_writer.graph import run_report_writer
from pipeline.storage.database import Database
from pipeline.storage.repositories import AgentRunRepository

logger = logging.getLogger(__name__)


class OrchestratorStateDict(TypedDict, total=False):
    """Top-level state for the full pipeline workflow."""

    status: str
    api_base_url: str
    freshness_threshold_hours: float
    ollama_model: str
    ollama_base_url: str
    ollama_timeout: float
    report_output_dir: str

    # sub-agent results
    monitor_result: dict | None
    analyst_result: dict | None
    report_writer_result: dict | None

    # tracking
    agent_run_id: int | None
    started_at: str
    completed_at: str | None
    tool_calls_succeeded: int
    tool_calls_failed: int
    error: str | None
    output_path: str | None


def _count_tools(result: dict | None) -> tuple[int, int]:
    """Count succeeded/failed tool calls from a sub-agent result."""
    if result is None:
        return 0, 0
    tools = result.get("tool_results", [])
    ok = sum(1 for t in tools if t.get("success"))
    fail = sum(1 for t in tools if not t.get("success"))
    return ok, fail


def build_orchestrator_graph(database: Database) -> StateGraph:
    """Construct the full pipeline orchestrator graph.

    Workflow:
        run_monitor → (should_trigger?) → run_analyst → run_report_writer → record_run
                                      ↘ (no trigger)  → record_run → END
    """
    agent_repo = AgentRunRepository(database)

    def monitor_node(state: OrchestratorStateDict) -> OrchestratorStateDict:
        url = state.get("api_base_url", "http://127.0.0.1:8000")
        threshold = state.get("freshness_threshold_hours", 168.0)
        result = run_monitor(database, freshness_threshold_hours=threshold, api_base_url=url)
        logger.info("Monitor finished: status=%s should_trigger=%s",
                     result.get("status"), result.get("should_trigger_analysis"))
        return {"monitor_result": result}

    def analyst_node(state: OrchestratorStateDict) -> OrchestratorStateDict:
        url = state.get("api_base_url", "http://127.0.0.1:8000")
        result = run_analyst(api_base_url=url)
        logger.info("Analyst finished: status=%s", result.get("status"))
        return {"analyst_result": result}

    def report_writer_node(state: OrchestratorStateDict) -> OrchestratorStateDict:
        analyst_result = state.get("analyst_result", {})
        analyst_report = analyst_result.get("report") if analyst_result else None

        if analyst_report is None:
            return {
                "report_writer_result": None,
                "error": "analyst produced no report",
            }

        result = run_report_writer(
            analyst_report=analyst_report,
            ollama_model=state.get("ollama_model", "llama3"),
            ollama_base_url=state.get("ollama_base_url", "http://localhost:11434"),
            ollama_timeout=state.get("ollama_timeout", 120.0),
        )
        logger.info("Report Writer finished: status=%s", result.get("status"))

        output_path = None
        md = result.get("report_markdown", "")
        if md:
            out_dir = Path(state.get("report_output_dir", "reports"))
            out_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            out_file = out_dir / f"report_{ts}.md"
            out_file.write_text(md, encoding="utf-8")
            output_path = str(out_file)
            logger.info("Report saved to %s", output_path)

        return {"report_writer_result": result, "output_path": output_path}

    def record_run_node(state: OrchestratorStateDict) -> OrchestratorStateDict:
        started_str = state.get("started_at", datetime.now(timezone.utc).isoformat())
        now = datetime.now(timezone.utc)

        ok_total, fail_total = 0, 0
        for key in ("monitor_result", "analyst_result", "report_writer_result"):
            ok, fail = _count_tools(state.get(key))
            ok_total += ok
            fail_total += fail

        monitor = state.get("monitor_result") or {}
        analyst = state.get("analyst_result")
        rw = state.get("report_writer_result")

        if monitor.get("status") == "error":
            final_status = "monitor_error"
            error = monitor.get("error")
            from pipeline.monitoring.recorder import record_agent_failure

            record_agent_failure(agent="monitor", detail=error)
        elif not monitor.get("should_trigger_analysis"):
            final_status = f"skipped:{monitor.get('status', 'unknown')}"
            error = None
        elif analyst and analyst.get("status") == "error":
            final_status = "analyst_error"
            error = analyst.get("error")
            from pipeline.monitoring.recorder import record_agent_failure

            record_agent_failure(agent="analyst", detail=error)
        elif rw and rw.get("status") in ("completed", "completed_fallback"):
            final_status = "completed"
            error = None
        elif rw and rw.get("status") == "invalid_input":
            final_status = "report_writer_error"
            error = rw.get("error")
            from pipeline.monitoring.recorder import record_agent_failure

            record_agent_failure(agent="report_writer", detail=error)
        else:
            final_status = "completed_partial"
            error = state.get("error")
            if error:
                from pipeline.monitoring.recorder import record_agent_failure

                record_agent_failure(agent="orchestrator", detail=error)
        run_id = agent_repo.create(
            started_at=datetime.fromisoformat(started_str),
            completed_at=now,
            status=final_status,
            workflow_name="v1_pipeline_orchestrator",
            tool_calls_succeeded=ok_total,
            tool_calls_failed=fail_total,
            output_path=state.get("output_path"),
            error_message=error,
        )
        logger.info("Agent run recorded: id=%s status=%s", run_id, final_status)

        return {
            "status": final_status,
            "agent_run_id": run_id,
            "completed_at": now.isoformat(),
            "tool_calls_succeeded": ok_total,
            "tool_calls_failed": fail_total,
            "error": error,
        }

    def _after_monitor(state: OrchestratorStateDict) -> str:
        monitor = state.get("monitor_result") or {}
        if monitor.get("should_trigger_analysis"):
            return "analyst"
        return "record_run"

    graph = StateGraph(OrchestratorStateDict)

    graph.add_node("monitor", monitor_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("report_writer", report_writer_node)
    graph.add_node("record_run", record_run_node)

    graph.set_entry_point("monitor")

    graph.add_conditional_edges("monitor", _after_monitor, {
        "analyst": "analyst",
        "record_run": "record_run",
    })
    graph.add_edge("analyst", "report_writer")
    graph.add_edge("report_writer", "record_run")
    graph.add_edge("record_run", END)

    return graph


def run_orchestrator(
    database: Database,
    api_base_url: str = "http://127.0.0.1:8000",
    freshness_threshold_hours: float = 168.0,
    ollama_model: str = "llama3",
    ollama_base_url: str = "http://localhost:11434",
    ollama_timeout: float = 120.0,
    report_output_dir: str = "reports",
) -> dict:
    """Build, compile, and invoke the full pipeline orchestrator."""
    graph = build_orchestrator_graph(database)
    compiled = graph.compile()

    now = datetime.now(timezone.utc)
    initial_state: OrchestratorStateDict = {
        "status": "pending",
        "api_base_url": api_base_url,
        "freshness_threshold_hours": freshness_threshold_hours,
        "ollama_model": ollama_model,
        "ollama_base_url": ollama_base_url,
        "ollama_timeout": ollama_timeout,
        "report_output_dir": report_output_dir,
        "monitor_result": None,
        "analyst_result": None,
        "report_writer_result": None,
        "agent_run_id": None,
        "started_at": now.isoformat(),
        "completed_at": None,
        "tool_calls_succeeded": 0,
        "tool_calls_failed": 0,
        "error": None,
        "output_path": None,
    }

    return compiled.invoke(initial_state)
