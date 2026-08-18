"""V1 skill taxonomy configuration and lookup."""

from pathlib import Path

from pipeline.skills.exceptions import TaxonomyError
from pipeline.skills.models import SkillDefinition
from pipeline.skills.taxonomy import DEFAULT_TAXONOMY_PATH, SkillTaxonomy

__all__ = [
    "DEFAULT_TAXONOMY_PATH",
    "SkillDefinition",
    "SkillTaxonomy",
    "TaxonomyError",
    "load_taxonomy",
]


def load_taxonomy(path: Path | None = None) -> SkillTaxonomy:
    """Load the skill taxonomy from the default or provided path."""
    return SkillTaxonomy.from_path(path)
