"""Structured output types for the Analyst Agent.

These models define the analysis report that downstream agents (e.g. the
Report Writer) will consume.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SignalStrength(str, Enum):
    STRONG = "strong"
    WEAK = "weak"


class MovementDirection(str, Enum):
    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SkillMovement:
    """A single skill's interpreted trend movement."""

    skill: str
    direction: MovementDirection
    signal_strength: SignalStrength
    current_mentions: int
    previous_mentions: int
    change: int
    change_percent: float | None
    z_score: float | None
    raw_trend: str
    raw_direction: str


@dataclass(frozen=True)
class AnalysisReport:
    """Complete analyst output, ready for the Report Writer.

    Fields
    ------
    model_version : str
        ML model version that produced the underlying trend data.
    generated_at : datetime
        When the trend data was generated.
    analyzed_at : datetime
        When this analysis was performed.
    period_count : int
        Number of time periods the model evaluated.
    total_skills_in_model : int
        Total skills returned by the ML API.
    strong_signals : list[SkillMovement]
        Skills with high-confidence movements (z-score available or
        large change_percent).
    weak_signals : list[SkillMovement]
        Skills with low-confidence or insufficient-data movements.
    top_risers : list[SkillMovement]
        Top rising skills ranked by z-score then change_percent.
    top_fallers : list[SkillMovement]
        Top falling skills ranked by z-score then change_percent.
    stable_skills : list[str]
        Skills that show no significant movement.
    data_quality_notes : list[str]
        Warnings about data limitations (e.g. insufficient history).
    """

    model_version: str
    generated_at: datetime
    analyzed_at: datetime
    period_count: int
    total_skills_in_model: int
    strong_signals: list[SkillMovement]
    weak_signals: list[SkillMovement]
    top_risers: list[SkillMovement]
    top_fallers: list[SkillMovement]
    stable_skills: list[str]
    data_quality_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON output / Report Writer."""
        def _movement(m: SkillMovement) -> dict:
            return {
                "skill": m.skill,
                "direction": m.direction.value,
                "signal_strength": m.signal_strength.value,
                "current_mentions": m.current_mentions,
                "previous_mentions": m.previous_mentions,
                "change": m.change,
                "change_percent": m.change_percent,
                "z_score": m.z_score,
                "raw_trend": m.raw_trend,
                "raw_direction": m.raw_direction,
            }

        return {
            "model_version": self.model_version,
            "generated_at": self.generated_at.isoformat(),
            "analyzed_at": self.analyzed_at.isoformat(),
            "period_count": self.period_count,
            "total_skills_in_model": self.total_skills_in_model,
            "strong_signals": [_movement(m) for m in self.strong_signals],
            "weak_signals": [_movement(m) for m in self.weak_signals],
            "top_risers": [_movement(m) for m in self.top_risers],
            "top_fallers": [_movement(m) for m in self.top_fallers],
            "stable_skills": self.stable_skills,
            "data_quality_notes": self.data_quality_notes,
        }
