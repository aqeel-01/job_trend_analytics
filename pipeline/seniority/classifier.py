"""Deterministic seniority classification from job title and description."""

import re

from pipeline.preprocess.text import preprocess_description
from pipeline.seniority.models import (
    CONFIDENCE_DESCRIPTION_MATCH,
    CONFIDENCE_TITLE_MATCH,
    CONFIDENCE_UNKNOWN,
    SeniorityLevel,
    SeniorityResult,
)
from pipeline.seniority.rules import SENIORITY_RULES


def _normalize_title(title: str | None) -> str:
    if title is None:
        return ""
    if not isinstance(title, str):
        title = str(title)
    return preprocess_description(title)


def _compile_rules() -> list[tuple[SeniorityLevel, re.Pattern[str], str]]:
    compiled: list[tuple[SeniorityLevel, re.Pattern[str], str]] = []
    for rule in SENIORITY_RULES:
        level = SeniorityLevel(rule.level)
        for pattern in rule.patterns:
            compiled.append(
                (
                    level,
                    re.compile(pattern, re.IGNORECASE),
                    f"{rule.level}: {rule.description} ({pattern})",
                )
            )
    return compiled


_COMPILED_RULES = _compile_rules()


def _match_text(
    text: str,
    source: str,
    confidence: float,
) -> SeniorityResult | None:
    if not text:
        return None

    for level, pattern, rule_description in _COMPILED_RULES:
        match = pattern.search(text)
        if match is not None:
            return SeniorityResult(
                level=level,
                confidence=confidence,
                matched_term=match.group(0),
                matched_rule=rule_description,
                source=source,
            )
    return None


def classify_seniority(
    title: str | None,
    description: str | None = None,
) -> SeniorityResult:
    """
    Classify approximate seniority using deterministic title-first rules.

    1. Normalize title and description text.
    2. Apply ordered rules to the title (highest confidence).
    3. If no title match, apply the same rules to the description.
    4. Return unknown when no rule matches.
    """
    normalized_title = _normalize_title(title)
    title_result = _match_text(
        normalized_title,
        source="title",
        confidence=CONFIDENCE_TITLE_MATCH,
    )
    if title_result is not None:
        return title_result

    normalized_description = preprocess_description(description)
    description_result = _match_text(
        normalized_description,
        source="description",
        confidence=CONFIDENCE_DESCRIPTION_MATCH,
    )
    if description_result is not None:
        return description_result

    return SeniorityResult(
        level=SeniorityLevel.UNKNOWN,
        confidence=CONFIDENCE_UNKNOWN,
        matched_term=None,
        matched_rule="no seniority signal found",
        source="none",
    )
