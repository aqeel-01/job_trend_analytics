"""Shared fixtures for Report Writer tests."""

import pytest

VALID_ANALYST_REPORT = {
    "model_version": "v1.0",
    "generated_at": "2026-08-19T12:00:00Z",
    "analyzed_at": "2026-08-19T12:01:00Z",
    "period_count": 4,
    "total_skills_in_model": 5,
    "strong_signals": [
        {
            "skill": "Python",
            "direction": "rising",
            "signal_strength": "strong",
            "current_mentions": 80,
            "previous_mentions": 40,
            "change": 40,
            "change_percent": 100.0,
            "z_score": 9.0,
            "raw_trend": "rising",
            "raw_direction": "up",
        },
        {
            "skill": "Java",
            "direction": "falling",
            "signal_strength": "strong",
            "current_mentions": 30,
            "previous_mentions": 50,
            "change": -20,
            "change_percent": -40.0,
            "z_score": -3.0,
            "raw_trend": "falling",
            "raw_direction": "down",
        },
    ],
    "weak_signals": [
        {
            "skill": "Rust",
            "direction": "unknown",
            "signal_strength": "weak",
            "current_mentions": 15,
            "previous_mentions": 3,
            "change": 12,
            "change_percent": 400.0,
            "z_score": None,
            "raw_trend": "insufficient_data",
            "raw_direction": "unknown",
        },
    ],
    "top_risers": [
        {
            "skill": "Python",
            "direction": "rising",
            "signal_strength": "strong",
            "current_mentions": 80,
            "previous_mentions": 40,
            "change": 40,
            "change_percent": 100.0,
            "z_score": 9.0,
            "raw_trend": "rising",
            "raw_direction": "up",
        },
    ],
    "top_fallers": [
        {
            "skill": "Java",
            "direction": "falling",
            "signal_strength": "strong",
            "current_mentions": 30,
            "previous_mentions": 50,
            "change": -20,
            "change_percent": -40.0,
            "z_score": -3.0,
            "raw_trend": "falling",
            "raw_direction": "down",
        },
    ],
    "stable_skills": ["Go"],
    "data_quality_notes": ["2 of 5 skills lack sufficient history for z-score computation."],
}


@pytest.fixture
def valid_analyst_report():
    return VALID_ANALYST_REPORT.copy()
