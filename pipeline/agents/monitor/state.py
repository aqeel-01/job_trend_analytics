"""Monitor Agent state definition."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class MonitorStatus(str, Enum):
    PENDING = "pending"
    CHECKING = "checking"
    HEALTHY = "healthy"
    STALE = "stale"
    FAILURE_DETECTED = "failure_detected"
    ANALYSIS_TRIGGERED = "analysis_triggered"
    ERROR = "error"


@dataclass
class ToolResult:
    """Outcome of a single monitor tool invocation."""

    tool_name: str
    success: bool
    detail: str
    checked_at: datetime = field(default_factory=lambda: datetime.now())


@dataclass
class MonitorState:
    """Shared state threaded through the LangGraph monitor workflow.

    LangGraph nodes receive and return this state dict (as TypedDict),
    but we define the shape here for clarity and reuse in tests.
    """

    status: str = MonitorStatus.PENDING.value
    db_healthy: bool | None = None
    pipeline_fresh: bool | None = None
    api_healthy: bool | None = None
    new_data_exists: bool | None = None
    ingestion_failure: bool | None = None
    last_run_at: str | None = None
    job_count: int = 0
    skill_link_count: int = 0
    freshness_threshold_hours: float = 168.0  # 7 days default
    tool_results: list[dict] = field(default_factory=list)
    error: str | None = None
    should_trigger_analysis: bool = False
