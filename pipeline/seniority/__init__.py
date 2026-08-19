"""Deterministic approximate seniority detection for V1."""

from pipeline.seniority.classifier import classify_seniority
from pipeline.seniority.models import (
    CONFIDENCE_DESCRIPTION_MATCH,
    CONFIDENCE_TITLE_MATCH,
    CONFIDENCE_UNKNOWN,
    SeniorityLevel,
    SeniorityResult,
)
from pipeline.seniority.rules import SENIORITY_RULES, SeniorityRule

__all__ = [
    "CONFIDENCE_DESCRIPTION_MATCH",
    "CONFIDENCE_TITLE_MATCH",
    "CONFIDENCE_UNKNOWN",
    "SeniorityLevel",
    "SeniorityResult",
    "SeniorityRule",
    "SENIORITY_RULES",
    "classify_seniority",
]
