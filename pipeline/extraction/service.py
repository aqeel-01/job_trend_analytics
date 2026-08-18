"""Persist extracted skills and integrate with SQLite storage."""

import json
from dataclasses import dataclass
from pathlib import Path

from pipeline.config.settings import PROJECT_ROOT
from pipeline.extraction.matcher import DeterministicSkillMatcher
from pipeline.extraction.models import ExtractionResult, ExtractedSkill
from pipeline.skills.taxonomy import SkillTaxonomy
from pipeline.storage.repositories import JobSkillRepository, SkillRepository

DEFAULT_EVALUATION_DATASET_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "skill_extraction_labels.json"
)


@dataclass(frozen=True)
class EvaluationSample:
    """A single manually labelable evaluation record."""

    id: str
    description: str
    labeled_skills: tuple[str, ...]
    notes: str | None = None


@dataclass(frozen=True)
class EvaluationDataset:
    """Manual skill extraction evaluation dataset structure."""

    version: str
    description: str
    labeling_instructions: str
    target_sample_count: str
    metrics: tuple[str, ...]
    samples: tuple[EvaluationSample, ...]


class SkillExtractionService:
    """Extract skills from descriptions and persist links to SQLite."""

    def __init__(
        self,
        matcher: DeterministicSkillMatcher,
        skill_repository: SkillRepository,
        job_skill_repository: JobSkillRepository,
        taxonomy: SkillTaxonomy,
    ) -> None:
        self.matcher = matcher
        self.skill_repository = skill_repository
        self.job_skill_repository = job_skill_repository
        self.taxonomy = taxonomy

    def extract_from_text(self, text: str | None) -> ExtractionResult:
        """Preprocess and extract skills without persisting."""
        return self.matcher.extract_from_raw(text)

    def extract_and_store(self, job_id: int, description: str | None) -> ExtractionResult:
        """Extract skills from a job description and persist to skills/job_skills."""
        result = self.extract_from_text(description)
        for skill in result.skills:
            skill_def = self.taxonomy.get_skill(skill.canonical_name)
            category = skill_def.category if skill_def is not None else None
            skill_id = self.skill_repository.get_or_create_by_canonical(
                canonical_name=skill.canonical_name,
                category=category,
            )
            self.job_skill_repository.link(
                job_id=job_id,
                skill_id=skill_id,
                confidence=skill.confidence,
                extraction_method=skill.extraction_method,
            )
        return result


def load_evaluation_dataset(path: Path | None = None) -> EvaluationDataset:
    """Load the manual skill extraction evaluation dataset structure."""
    dataset_path = path or DEFAULT_EVALUATION_DATASET_PATH
    if not dataset_path.is_file():
        raise FileNotFoundError(f"Evaluation dataset not found: {dataset_path}")

    with dataset_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    raw_samples = payload.get("samples", [])
    samples: list[EvaluationSample] = []
    for raw in raw_samples:
        labeled = raw.get("labeled_skills", [])
        if labeled is None:
            labeled_skills: tuple[str, ...] = ()
        else:
            labeled_skills = tuple(str(skill) for skill in labeled)

        samples.append(
            EvaluationSample(
                id=str(raw["id"]),
                description=str(raw["description"]),
                labeled_skills=labeled_skills,
                notes=raw.get("notes"),
            )
        )

    metrics = tuple(str(metric) for metric in payload.get("metrics", ()))

    return EvaluationDataset(
        version=str(payload.get("version", "1.0")),
        description=str(payload.get("description", "")),
        labeling_instructions=str(payload.get("labeling_instructions", "")),
        target_sample_count=str(payload.get("target_sample_count", "")),
        metrics=metrics,
        samples=tuple(samples),
    )
