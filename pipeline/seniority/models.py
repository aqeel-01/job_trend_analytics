"""Seniority detection result types."""

from dataclasses import dataclass
from enum import StrEnum


class SeniorityLevel(StrEnum):
    """Approximate seniority categories for V1."""

    INTERN = "intern"
    ENTRY = "entry"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    UNKNOWN = "unknown"


CONFIDENCE_TITLE_MATCH = 0.9
CONFIDENCE_DESCRIPTION_MATCH = 0.7
CONFIDENCE_UNKNOWN = 0.5


@dataclass(frozen=True)
class SeniorityResult:
    """Outcome of deterministic seniority classification."""

    level: SeniorityLevel
    confidence: float
    matched_term: str | None
    matched_rule: str
    source: str
