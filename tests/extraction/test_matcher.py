"""Tests for deterministic skill matching."""

import pytest

from pipeline.extraction.matcher import DeterministicSkillMatcher
from pipeline.extraction.models import (
    CONFIDENCE_ALIAS_MATCH,
    CONFIDENCE_CANONICAL_MATCH,
    EXTRACTION_METHOD_DETERMINISTIC,
)
from pipeline.skills import load_taxonomy


@pytest.fixture
def matcher() -> DeterministicSkillMatcher:
    return DeterministicSkillMatcher(load_taxonomy())


def _canonical_names(result) -> set[str]:
    return {skill.canonical_name for skill in result.skills}


def test_exact_skill_match(matcher: DeterministicSkillMatcher) -> None:
    result = matcher.extract_from_raw(
        "Experience with Python, Docker and AWS is required."
    )

    assert _canonical_names(result) == {"Python", "Docker", "AWS"}
    python = next(skill for skill in result.skills if skill.canonical_name == "Python")
    assert python.confidence == CONFIDENCE_CANONICAL_MATCH
    assert python.extraction_method == EXTRACTION_METHOD_DETERMINISTIC


def test_alias_resolution(matcher: DeterministicSkillMatcher) -> None:
    result = matcher.extract_from_raw(
        "Must know postgres, k8s, and scikit learn for this role."
    )

    assert _canonical_names(result) == {"PostgreSQL", "Kubernetes", "Scikit-learn"}
    postgres = next(skill for skill in result.skills if skill.canonical_name == "PostgreSQL")
    assert postgres.confidence == CONFIDENCE_ALIAS_MATCH


def test_multiple_skills(matcher: DeterministicSkillMatcher) -> None:
    result = matcher.extract_from_raw(
        "Stack includes FastAPI, Django, React, Angular, and MongoDB."
    )

    assert _canonical_names(result) == {
        "FastAPI",
        "Django",
        "React",
        "Angular",
        "MongoDB",
    }


def test_repeated_mentions_counted(matcher: DeterministicSkillMatcher) -> None:
    result = matcher.extract_from_raw(
        "Python developer with Python experience and daily Python scripting."
    )

    python = next(skill for skill in result.skills if skill.canonical_name == "Python")
    assert python.mention_count == 3
    assert len(result.skills) == 1


def test_case_insensitive_matching(matcher: DeterministicSkillMatcher) -> None:
    result = matcher.extract_from_raw("Required: PYTHON, docker, JaVaScRiPt")

    assert _canonical_names(result) == {"Python", "Docker", "JavaScript"}


def test_no_false_partial_match_java_in_javascript(matcher: DeterministicSkillMatcher) -> None:
    result = matcher.extract_from_raw("We need a JavaScript engineer for frontend work.")

    assert _canonical_names(result) == {"JavaScript"}
    assert "Java" not in _canonical_names(result)


def test_no_false_partial_match_sql_in_mysql(matcher: DeterministicSkillMatcher) -> None:
    result = matcher.extract_from_raw("Primary database is MySQL.")

    assert _canonical_names(result) == {"MySQL"}
    assert "SQL" not in _canonical_names(result)


def test_no_duplicate_skill_results(matcher: DeterministicSkillMatcher) -> None:
    result = matcher.extract_from_raw("Python, PYTHON, python, and Py experience.")

    assert len(result.skills) == 1
    assert result.skills[0].canonical_name == "Python"


def test_empty_description_returns_no_skills(matcher: DeterministicSkillMatcher) -> None:
    result = matcher.extract_from_raw(None)
    assert result.skills == ()
    assert result.normalized_text == ""
