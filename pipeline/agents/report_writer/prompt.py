"""Prompt construction for the Report Writer Agent.

Builds a structured prompt from the Analyst report dict so the LLM generates
a grounded report without fabricating evidence.
"""

from __future__ import annotations

import json


SYSTEM_PROMPT = """\
You are a professional job-market analyst writing a concise weekly report.

STRICT RULES:
1. Only reference skills and statistics provided in the DATA section below.
2. Never invent, fabricate, or hallucinate statistics, percentages, or skill names.
3. Clearly distinguish between strong signals (high confidence) and weak signals (low confidence).
4. When data is insufficient, say so explicitly rather than guessing.
5. Use the exact numbers from the data (mentions, change_percent, z_score).
6. Include a limitations section acknowledging data constraints.

OUTPUT FORMAT:
Write the report in markdown with these sections:
- **Executive Summary**: 2-3 sentence overview of the week's trends.
- **Rising Skills**: Skills with upward momentum, citing evidence (mentions, change%, z-score).
- **Declining Skills**: Skills with downward momentum, citing evidence.
- **Stable Skills**: Skills showing no significant change.
- **Weak Signals**: Skills where the evidence is uncertain or data is insufficient.
- **Methodology Note**: Briefly state the model version and method used.

Do NOT add sections beyond these. Do NOT reference external sources."""


def build_report_prompt(analyst_report: dict) -> str:
    """Build the user prompt from the Analyst's structured output."""
    data_section = _format_data_section(analyst_report)
    return f"""\
Generate a weekly job-market skill-demand report based ONLY on the following data.

DATA:
{data_section}

Write the report now, following the format specified in your instructions."""


def _format_data_section(report: dict) -> str:
    """Format the analyst report into a readable data block for the LLM."""
    parts: list[str] = []

    parts.append(f"Model Version: {report.get('model_version', 'unknown')}")
    parts.append(f"Analysis Period Count: {report.get('period_count', 0)}")
    parts.append(f"Total Skills Analyzed: {report.get('total_skills_in_model', 0)}")
    parts.append("")

    strong = report.get("strong_signals", [])
    if strong:
        parts.append("STRONG SIGNALS (high confidence):")
        for s in strong:
            parts.append(_format_skill_line(s))
        parts.append("")

    weak = report.get("weak_signals", [])
    if weak:
        parts.append("WEAK SIGNALS (low confidence / insufficient data):")
        for s in weak:
            parts.append(_format_skill_line(s))
        parts.append("")

    risers = report.get("top_risers", [])
    if risers:
        parts.append("TOP RISING SKILLS:")
        for s in risers:
            parts.append(f"  - {s.get('skill')}: +{s.get('change', 0)} mentions "
                         f"({s.get('current_mentions', 0)} current)")
        parts.append("")

    fallers = report.get("top_fallers", [])
    if fallers:
        parts.append("TOP FALLING SKILLS:")
        for s in fallers:
            parts.append(f"  - {s.get('skill')}: {s.get('change', 0)} mentions "
                         f"({s.get('current_mentions', 0)} current)")
        parts.append("")

    stable = report.get("stable_skills", [])
    if stable:
        parts.append(f"STABLE SKILLS: {', '.join(stable)}")
        parts.append("")

    notes = report.get("data_quality_notes", [])
    if notes:
        parts.append("DATA QUALITY NOTES:")
        for n in notes:
            parts.append(f"  - {n}")
        parts.append("")

    return "\n".join(parts)


def _format_skill_line(s: dict) -> str:
    z = s.get("z_score")
    z_str = f"z={z:.2f}" if z is not None else "z=N/A"
    cp = s.get("change_percent")
    cp_str = f"{cp:+.1f}%" if cp is not None else "N/A"
    return (
        f"  - {s.get('skill')}: {s.get('direction', '?')} | "
        f"signal={s.get('signal_strength', '?')} | "
        f"mentions {s.get('previous_mentions', 0)}→{s.get('current_mentions', 0)} "
        f"(change {cp_str}) | {z_str}"
    )
