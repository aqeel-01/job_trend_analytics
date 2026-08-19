"""Deterministic seniority classification rules for V1.

Rules are evaluated in priority order (top wins). Job title is checked first;
description is used only when the title has no match.

Categories
----------
- intern: internship or trainee roles
- entry: explicit entry-level or graduate hiring signals
- junior: junior or jr. markers
- lead: principal, staff, distinguished, lead, or head-of signals
- senior: senior or sr. markers
- mid: explicit mid-level or intermediate markers
- unknown: no reliable seniority signal found

Title matches are preferred over description matches because titles are more
direct indicators of seniority in job postings.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SeniorityRule:
    """A single seniority rule with human-readable documentation."""

    level: str
    patterns: tuple[str, ...]
    description: str


SENIORITY_RULES: tuple[SeniorityRule, ...] = (
    SeniorityRule(
        level="intern",
        patterns=(r"\bintern(?:ship)?\b", r"\btrainee\b"),
        description="Internship or trainee wording",
    ),
    SeniorityRule(
        level="entry",
        patterns=(
            r"\bentry[- ]level\b",
            r"\bgraduate\b",
            r"\bgrad\b",
            r"\bassociate\b",
        ),
        description="Entry-level or early-career graduate hiring signals",
    ),
    SeniorityRule(
        level="junior",
        patterns=(r"\bjunior\b", r"\bjr\.?\b"),
        description="Junior or jr. markers",
    ),
    SeniorityRule(
        level="lead",
        patterns=(
            r"\bprincipal\b",
            r"\bstaff\b",
            r"\bdistinguished\b",
            r"\btech lead\b",
            r"\bteam lead\b",
            r"\bengineering lead\b",
            r"\bhead of\b",
            r"\bengineering manager\b",
            r"\blead\b",
        ),
        description="Leadership, principal, staff, or management signals",
    ),
    SeniorityRule(
        level="senior",
        patterns=(r"\bsenior\b", r"\bsr\.?\b"),
        description="Senior or sr. markers",
    ),
    SeniorityRule(
        level="mid",
        patterns=(r"\bmid[- ]level\b", r"\bintermediate\b"),
        description="Explicit mid-level or intermediate markers",
    ),
)
