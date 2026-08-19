"""Tests for Analyst Agent output models."""

from datetime import datetime, timezone

from pipeline.agents.analyst.models import (
    AnalysisReport,
    MovementDirection,
    SignalStrength,
    SkillMovement,
)


def _make_movement(**overrides):
    defaults = dict(
        skill="Python",
        direction=MovementDirection.RISING,
        signal_strength=SignalStrength.STRONG,
        current_mentions=80,
        previous_mentions=40,
        change=40,
        change_percent=100.0,
        z_score=9.0,
        raw_trend="rising",
        raw_direction="up",
    )
    defaults.update(overrides)
    return SkillMovement(**defaults)


class TestAnalysisReport:
    def test_to_dict_serializable(self):
        now = datetime.now(timezone.utc)
        report = AnalysisReport(
            model_version="v1.0",
            generated_at=now,
            analyzed_at=now,
            period_count=4,
            total_skills_in_model=1,
            strong_signals=[_make_movement()],
            weak_signals=[],
            top_risers=[_make_movement()],
            top_fallers=[],
            stable_skills=["Go"],
            data_quality_notes=["test note"],
        )
        d = report.to_dict()
        assert d["model_version"] == "v1.0"
        assert len(d["strong_signals"]) == 1
        assert d["strong_signals"][0]["skill"] == "Python"
        assert d["stable_skills"] == ["Go"]
        assert d["data_quality_notes"] == ["test note"]

    def test_to_dict_handles_none_z_score(self):
        m = _make_movement(z_score=None, change_percent=None)
        report = AnalysisReport(
            model_version="v1.0",
            generated_at=datetime.now(timezone.utc),
            analyzed_at=datetime.now(timezone.utc),
            period_count=1,
            total_skills_in_model=1,
            strong_signals=[m],
            weak_signals=[],
            top_risers=[],
            top_fallers=[],
            stable_skills=[],
        )
        d = report.to_dict()
        assert d["strong_signals"][0]["z_score"] is None
