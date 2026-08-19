"""Structured output for the Report Writer Agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ReportSection:
    """A named section of the weekly report."""

    heading: str
    body: str


@dataclass
class WeeklyReport:
    """Final weekly job-market report output."""

    title: str
    generated_at: datetime
    model_version: str
    period_count: int
    total_skills_analyzed: int
    sections: list[ReportSection] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    llm_model_used: str = ""
    raw_llm_response: str = ""

    def to_markdown(self) -> str:
        lines = [f"# {self.title}", ""]
        lines.append(f"*Generated: {self.generated_at.isoformat()}*  ")
        lines.append(f"*Model: {self.model_version} | LLM: {self.llm_model_used} | "
                      f"Periods: {self.period_count} | Skills: {self.total_skills_analyzed}*")
        lines.append("")

        for section in self.sections:
            lines.append(f"## {section.heading}")
            lines.append("")
            lines.append(section.body)
            lines.append("")

        if self.limitations:
            lines.append("## Limitations & Caveats")
            lines.append("")
            for note in self.limitations:
                lines.append(f"- {note}")
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "generated_at": self.generated_at.isoformat(),
            "model_version": self.model_version,
            "period_count": self.period_count,
            "total_skills_analyzed": self.total_skills_analyzed,
            "sections": [{"heading": s.heading, "body": s.body} for s in self.sections],
            "limitations": self.limitations,
            "llm_model_used": self.llm_model_used,
        }
