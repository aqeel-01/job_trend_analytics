"""Load and query the V1 skill taxonomy from configuration data."""

import json
import re
from pathlib import Path

from pipeline.config.settings import PROJECT_ROOT
from pipeline.skills.exceptions import TaxonomyError
from pipeline.skills.models import SkillDefinition

DEFAULT_TAXONOMY_PATH = PROJECT_ROOT / "data" / "skills_taxonomy.json"
_ALIAS_COLLAPSE_RE = re.compile(r"\s+")


def _normalize_lookup_key(value: str) -> str:
    """Normalize a term for case-insensitive alias lookup."""
    collapsed = _ALIAS_COLLAPSE_RE.sub(" ", value.strip().lower())
    return collapsed


class SkillTaxonomy:
    """In-memory skill taxonomy loaded from JSON configuration."""

    def __init__(self, skills: list[SkillDefinition], version: str = "1.0") -> None:
        self.version = version
        self._skills = tuple(skills)
        self._by_canonical: dict[str, SkillDefinition] = {}
        self._alias_map: dict[str, str] = {}

        for skill in self._skills:
            canonical_key = _normalize_lookup_key(skill.canonical_name)
            if canonical_key in self._alias_map:
                raise TaxonomyError(
                    f"Duplicate canonical name after normalization: {skill.canonical_name}"
                )
            self._by_canonical[skill.canonical_name] = skill
            self._alias_map[canonical_key] = skill.canonical_name

            for alias in skill.aliases:
                alias_key = _normalize_lookup_key(alias)
                if alias_key in self._alias_map:
                    existing = self._alias_map[alias_key]
                    if existing != skill.canonical_name:
                        raise TaxonomyError(
                            f"Alias '{alias}' maps to both '{existing}' and '{skill.canonical_name}'"
                        )
                    continue
                self._alias_map[alias_key] = skill.canonical_name

    @classmethod
    def from_path(cls, path: Path | None = None) -> "SkillTaxonomy":
        """Load taxonomy from a JSON configuration file."""
        taxonomy_path = path or DEFAULT_TAXONOMY_PATH
        if not taxonomy_path.is_file():
            raise TaxonomyError(f"Skill taxonomy file not found: {taxonomy_path}")

        with taxonomy_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)

        if not isinstance(payload, dict):
            raise TaxonomyError("Skill taxonomy root must be a JSON object")

        version = str(payload.get("version", "1.0"))
        raw_skills = payload.get("skills")
        if not isinstance(raw_skills, list):
            raise TaxonomyError("Skill taxonomy must contain a 'skills' list")

        skills: list[SkillDefinition] = []
        seen_canonical: set[str] = set()

        for index, raw in enumerate(raw_skills):
            if not isinstance(raw, dict):
                raise TaxonomyError(f"Skill entry at index {index} must be an object")

            canonical_name = raw.get("canonical_name")
            category = raw.get("category")
            aliases = raw.get("aliases", [])

            if not canonical_name or not isinstance(canonical_name, str):
                raise TaxonomyError(f"Skill entry at index {index} missing canonical_name")
            if not category or not isinstance(category, str):
                raise TaxonomyError(
                    f"Skill entry '{canonical_name}' missing category"
                )
            if not isinstance(aliases, list):
                raise TaxonomyError(
                    f"Skill entry '{canonical_name}' aliases must be a list"
                )

            canonical_stripped = canonical_name.strip()
            if not canonical_stripped:
                raise TaxonomyError(f"Skill entry at index {index} has empty canonical_name")
            if canonical_stripped in seen_canonical:
                raise TaxonomyError(f"Duplicate canonical_name: {canonical_stripped}")

            seen_canonical.add(canonical_stripped)
            alias_tuple = tuple(str(alias).strip() for alias in aliases if str(alias).strip())

            skills.append(
                SkillDefinition(
                    canonical_name=canonical_stripped,
                    category=category.strip(),
                    aliases=alias_tuple,
                )
            )

        return cls(skills=skills, version=version)

    @property
    def skills(self) -> tuple[SkillDefinition, ...]:
        """Return all skill definitions."""
        return self._skills

    def canonical_names(self) -> list[str]:
        """Return all canonical skill names in taxonomy order."""
        return [skill.canonical_name for skill in self._skills]

    def get_skill(self, canonical_name: str) -> SkillDefinition | None:
        """Fetch a skill definition by exact canonical name."""
        return self._by_canonical.get(canonical_name)

    def resolve(self, term: str) -> str | None:
        """Resolve a canonical name or alias to its canonical skill name."""
        if not term or not isinstance(term, str):
            return None
        if not term.strip():
            return None
        return self._alias_map.get(_normalize_lookup_key(term))

    def resolve_alias(self, alias: str) -> str | None:
        """Resolve an alias to its canonical skill name."""
        return self.resolve(alias)

    def __len__(self) -> int:
        return len(self._skills)
