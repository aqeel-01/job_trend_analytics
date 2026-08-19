"""Tests for deterministic seniority classification."""

from pipeline.seniority import classify_seniority
from pipeline.seniority.models import (
    CONFIDENCE_DESCRIPTION_MATCH,
    CONFIDENCE_TITLE_MATCH,
    CONFIDENCE_UNKNOWN,
    SeniorityLevel,
)


def test_senior_title() -> None:
    result = classify_seniority("Senior Software Engineer")

    assert result.level == SeniorityLevel.SENIOR
    assert result.source == "title"
    assert result.confidence == CONFIDENCE_TITLE_MATCH
    assert result.matched_term.lower() == "senior"


def test_junior_title() -> None:
    result = classify_seniority("Junior Python Developer")

    assert result.level == SeniorityLevel.JUNIOR
    assert result.source == "title"


def test_intern_title() -> None:
    result = classify_seniority("Software Engineering Intern")

    assert result.level == SeniorityLevel.INTERN
    assert result.source == "title"


def test_entry_level_title() -> None:
    result = classify_seniority("Entry-Level Data Analyst")

    assert result.level == SeniorityLevel.ENTRY
    assert result.source == "title"


def test_lead_title() -> None:
    result = classify_seniority("Principal Backend Engineer")

    assert result.level == SeniorityLevel.LEAD
    assert result.source == "title"


def test_mid_level_title() -> None:
    result = classify_seniority("Mid-Level DevOps Engineer")

    assert result.level == SeniorityLevel.MID
    assert result.source == "title"


def test_unknown_title_without_signals() -> None:
    result = classify_seniority("Software Engineer")

    assert result.level == SeniorityLevel.UNKNOWN
    assert result.source == "none"
    assert result.confidence == CONFIDENCE_UNKNOWN


def test_description_fallback_when_title_is_generic() -> None:
    result = classify_seniority(
        title="Backend Engineer",
        description="We are hiring a senior backend engineer with Docker experience.",
    )

    assert result.level == SeniorityLevel.SENIOR
    assert result.source == "description"
    assert result.confidence == CONFIDENCE_DESCRIPTION_MATCH


def test_title_takes_priority_over_description() -> None:
    result = classify_seniority(
        title="Junior Developer",
        description="Looking for a senior engineer with leadership experience.",
    )

    assert result.level == SeniorityLevel.JUNIOR
    assert result.source == "title"


def test_case_insensitive_matching() -> None:
    result = classify_seniority("SENIOR devOps ENGINEER")

    assert result.level == SeniorityLevel.SENIOR


def test_null_and_empty_inputs() -> None:
    result = classify_seniority(None, None)

    assert result.level == SeniorityLevel.UNKNOWN
    assert result.source == "none"


def test_no_false_senior_in_seniority_word() -> None:
    """Ensure word-boundary rules avoid spurious substring matches."""
    result = classify_seniority(
        title="Business Analyst",
        description="Strong interpersonal skills required.",
    )

    assert result.level == SeniorityLevel.UNKNOWN
