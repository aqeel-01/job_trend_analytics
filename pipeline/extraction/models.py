"""Skill extraction result types."""

from dataclasses import dataclass

EXTRACTION_METHOD_DETERMINISTIC = "deterministic_taxonomy_v1"
CONFIDENCE_CANONICAL_MATCH = 1.0
CONFIDENCE_ALIAS_MATCH = 0.9


@dataclass(frozen=True)
class ExtractedSkill:
    """A skill identified in job description text."""

    canonical_name: str
    confidence: float
    extraction_method: str
    mention_count: int = 1


@dataclass(frozen=True)
class ExtractionResult:
    """Outcome of skill extraction for a single job description."""

    skills: tuple[ExtractedSkill, ...]
    normalized_text: str
