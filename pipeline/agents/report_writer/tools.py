"""Report Writer Agent tools — Ollama client for local LLM report generation."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


def generate_with_ollama(
    system_prompt: str,
    user_prompt: str,
    model: str = "llama3",
    base_url: str = "http://localhost:11434",
    timeout: float = 120.0,
) -> dict:
    """Call the Ollama /api/generate endpoint.

    Returns a dict with keys:
        success (bool), text (str), model (str), detail (str).
    """
    try:
        resp = httpx.post(
            f"{base_url}/api/generate",
            json={
                "model": model,
                "system": system_prompt,
                "prompt": user_prompt,
                "stream": False,
            },
            timeout=timeout,
        )
        if resp.status_code != 200:
            return {
                "success": False,
                "text": "",
                "model": model,
                "detail": f"HTTP {resp.status_code}: {resp.text[:300]}",
            }
        body = resp.json()
        return {
            "success": True,
            "text": body.get("response", ""),
            "model": model,
            "detail": "ok",
        }
    except httpx.ConnectError:
        return {
            "success": False,
            "text": "",
            "model": model,
            "detail": "connection refused — Ollama not running",
        }
    except Exception as exc:
        logger.exception("Ollama generation failed")
        return {
            "success": False,
            "text": "",
            "model": model,
            "detail": f"error: {exc}",
        }


def validate_analyst_report(report: dict | None) -> dict:
    """Validate the analyst report has the minimum required fields.

    Returns a dict with keys:
        valid (bool), issues (list[str]).
    """
    if report is None:
        return {"valid": False, "issues": ["analyst report is None"]}

    issues: list[str] = []
    required_keys = ["model_version", "total_skills_in_model", "strong_signals", "weak_signals"]
    for key in required_keys:
        if key not in report:
            issues.append(f"missing required field: {key}")

    all_signals = report.get("strong_signals", []) + report.get("weak_signals", [])
    if not all_signals:
        issues.append("no skill signals (strong or weak) present — nothing to report")

    period_count = report.get("period_count", 0)
    if period_count < 1:
        issues.append(f"period_count is {period_count}; at least 1 period is needed")

    return {"valid": len(issues) == 0, "issues": issues}


def build_fallback_report_text(analyst_report: dict, issues: list[str]) -> str:
    """Generate a deterministic fallback report when the LLM is unavailable."""
    lines = ["# Weekly Job-Market Skill-Demand Report (Fallback)", ""]
    lines.append("*This report was generated without LLM assistance because the language "
                 "model was unavailable.*")
    lines.append("")

    lines.append("## Executive Summary")
    lines.append("")
    total = analyst_report.get("total_skills_in_model", 0)
    strong = analyst_report.get("strong_signals", [])
    weak = analyst_report.get("weak_signals", [])
    lines.append(f"Analysis covers {total} skills across "
                 f"{analyst_report.get('period_count', 0)} period(s). "
                 f"{len(strong)} strong signal(s) and {len(weak)} weak signal(s) detected.")
    lines.append("")

    risers = analyst_report.get("top_risers", [])
    if risers:
        lines.append("## Rising Skills")
        lines.append("")
        for s in risers:
            z = s.get("z_score")
            z_str = f"z-score {z:.2f}" if z is not None else "z-score N/A"
            cp = s.get("change_percent")
            cp_str = f"{cp:+.1f}%" if cp is not None else "N/A"
            lines.append(f"- **{s['skill']}**: {s.get('previous_mentions', 0)}→"
                         f"{s.get('current_mentions', 0)} mentions ({cp_str}), {z_str}")
        lines.append("")

    fallers = analyst_report.get("top_fallers", [])
    if fallers:
        lines.append("## Declining Skills")
        lines.append("")
        for s in fallers:
            z = s.get("z_score")
            z_str = f"z-score {z:.2f}" if z is not None else "z-score N/A"
            cp = s.get("change_percent")
            cp_str = f"{cp:+.1f}%" if cp is not None else "N/A"
            lines.append(f"- **{s['skill']}**: {s.get('previous_mentions', 0)}→"
                         f"{s.get('current_mentions', 0)} mentions ({cp_str}), {z_str}")
        lines.append("")

    stable = analyst_report.get("stable_skills", [])
    if stable:
        lines.append("## Stable Skills")
        lines.append("")
        lines.append(f"The following skills showed no significant movement: {', '.join(stable)}.")
        lines.append("")

    if weak:
        lines.append("## Weak Signals")
        lines.append("")
        for s in weak:
            lines.append(f"- **{s['skill']}**: insufficient data for reliable trend assessment")
        lines.append("")

    notes = analyst_report.get("data_quality_notes", [])
    if notes or issues:
        lines.append("## Limitations & Caveats")
        lines.append("")
        for n in notes:
            lines.append(f"- {n}")
        for i in issues:
            lines.append(f"- {i}")
        lines.append("")

    return "\n".join(lines)
