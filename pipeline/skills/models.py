"""Skill taxonomy record types."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillDefinition:
    """A single skill entry in the V1 taxonomy."""

    canonical_name: str
    category: str
    aliases: tuple[str, ...]
