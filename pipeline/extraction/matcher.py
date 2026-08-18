"""Deterministic taxonomy-based skill matching."""

import re
from collections import defaultdict

from pipeline.extraction.models import (
    CONFIDENCE_ALIAS_MATCH,
    CONFIDENCE_CANONICAL_MATCH,
    EXTRACTION_METHOD_DETERMINISTIC,
    ExtractedSkill,
    ExtractionResult,
)
from pipeline.preprocess.text import preprocess_description
from pipeline.skills.taxonomy import SkillTaxonomy


def _boundary_pattern(term: str) -> str:
    """Build a regex pattern with word-boundary-style lookarounds."""
    escaped = re.escape(term)
    return f"(?<![\\w]){escaped}(?![\\w])"


class DeterministicSkillMatcher:
    """Match canonical skills and aliases in normalized job description text."""

    def __init__(self, taxonomy: SkillTaxonomy) -> None:
        self.taxonomy = taxonomy
        self._patterns: list[tuple[re.Pattern[str], str, bool]] = []
        self._build_patterns()

    def _build_patterns(self) -> None:
        terms: list[tuple[str, str, bool]] = []

        for skill in self.taxonomy.skills:
            terms.append((skill.canonical_name, skill.canonical_name, False))
            canonical_key = skill.canonical_name.strip().lower()
            for alias in skill.aliases:
                alias_key = alias.strip().lower()
                if alias_key == canonical_key:
                    continue
                terms.append((alias, skill.canonical_name, True))

        terms.sort(key=lambda item: len(item[0]), reverse=True)

        seen_patterns: set[str] = set()
        for term, canonical, is_alias in terms:
            pattern_source = term.strip()
            if not pattern_source:
                continue
            pattern_key = pattern_source.lower()
            if pattern_key in seen_patterns:
                continue
            seen_patterns.add(pattern_key)
            compiled = re.compile(_boundary_pattern(pattern_source), re.IGNORECASE)
            self._patterns.append((compiled, canonical, is_alias))

    def extract(self, normalized_text: str) -> ExtractionResult:
        """Extract unique skills from already-normalized description text."""
        if not normalized_text:
            return ExtractionResult(skills=(), normalized_text="")

        matches: list[tuple[int, int, str, bool]] = []

        for pattern, canonical, is_alias in self._patterns:
            for match in pattern.finditer(normalized_text):
                matches.append((match.start(), match.end(), canonical, is_alias))

        matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))

        covered: set[int] = set()
        selected: list[tuple[str, bool]] = []

        for start, end, canonical, is_alias in matches:
            span = range(start, end)
            if any(index in covered for index in span):
                continue
            for index in span:
                covered.add(index)
            selected.append((canonical, not is_alias))

        aggregates: dict[str, dict[str, object]] = defaultdict(
            lambda: {"mentions": 0, "canonical_match": False}
        )
        for canonical, is_canonical_match in selected:
            aggregates[canonical]["mentions"] = int(aggregates[canonical]["mentions"]) + 1
            if is_canonical_match:
                aggregates[canonical]["canonical_match"] = True

        extracted: list[ExtractedSkill] = []
        for canonical in sorted(aggregates):
            data = aggregates[canonical]
            mentions = int(data["mentions"])
            canonical_match = bool(data["canonical_match"])
            confidence = (
                CONFIDENCE_CANONICAL_MATCH
                if canonical_match
                else CONFIDENCE_ALIAS_MATCH
            )
            extracted.append(
                ExtractedSkill(
                    canonical_name=canonical,
                    confidence=confidence,
                    extraction_method=EXTRACTION_METHOD_DETERMINISTIC,
                    mention_count=mentions,
                )
            )

        return ExtractionResult(skills=tuple(extracted), normalized_text=normalized_text)

    def extract_from_raw(self, text: str | None) -> ExtractionResult:
        """Preprocess raw description text and extract skills."""
        normalized = preprocess_description(text)
        return self.extract(normalized)
