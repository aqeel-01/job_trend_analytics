"""Tests for the V1 skill taxonomy."""

from pathlib import Path

import pytest

from pipeline.skills import DEFAULT_TAXONOMY_PATH, load_taxonomy
from pipeline.skills.exceptions import TaxonomyError
from pipeline.skills.taxonomy import SkillTaxonomy

SRS_SKILLS = [
    "Python",
    "Java",
    "JavaScript",
    "TypeScript",
    "C++",
    "SQL",
    "PostgreSQL",
    "MySQL",
    "MongoDB",
    "AWS",
    "Azure",
    "GCP",
    "Docker",
    "Kubernetes",
    "Git",
    "Linux",
    "FastAPI",
    "Django",
    "React",
    "Node.js",
    "Angular",
    "TensorFlow",
    "PyTorch",
    "Scikit-learn",
    "Pandas",
    "Spark",
    "Airflow",
    "Kafka",
    "LangChain",
    "LangGraph",
    "Machine Learning",
    "Deep Learning",
    "NLP",
    "LLM",
    "Generative AI",
]


@pytest.fixture
def taxonomy() -> SkillTaxonomy:
    return load_taxonomy()


def test_taxonomy_loads_correctly(taxonomy: SkillTaxonomy) -> None:
    assert DEFAULT_TAXONOMY_PATH.is_file()
    assert taxonomy.version == "1.0"
    assert len(taxonomy) == 35
    assert 30 <= len(taxonomy) <= 50

    canonical_names = taxonomy.canonical_names()
    for skill_name in SRS_SKILLS:
        assert skill_name in canonical_names


def test_canonical_names_are_unique(taxonomy: SkillTaxonomy) -> None:
    canonical_names = taxonomy.canonical_names()
    assert len(canonical_names) == len(set(canonical_names))

    for name in canonical_names:
        skill = taxonomy.get_skill(name)
        assert skill is not None
        assert skill.canonical_name == name


def test_aliases_resolve_to_canonical_skill(taxonomy: SkillTaxonomy) -> None:
    alias_cases = {
        "postgres": "PostgreSQL",
        "POSTGRESQL": "PostgreSQL",
        "sklearn": "Scikit-learn",
        "scikit learn": "Scikit-learn",
        "k8s": "Kubernetes",
        "js": "JavaScript",
        "node": "Node.js",
        "tf": "TensorFlow",
        "pytorch": "PyTorch",
        "ml": "Machine Learning",
        "deep learning": "Deep Learning",
        "natural language processing": "NLP",
        "llms": "LLM",
        "genai": "Generative AI",
        "fast api": "FastAPI",
        "google cloud platform": "GCP",
    }

    for alias, expected in alias_cases.items():
        assert taxonomy.resolve_alias(alias) == expected
        assert taxonomy.resolve(alias) == expected


def test_canonical_name_self_resolution(taxonomy: SkillTaxonomy) -> None:
    assert taxonomy.resolve("Python") == "Python"
    assert taxonomy.resolve("python") == "Python"
    assert taxonomy.resolve("PostgreSQL") == "PostgreSQL"


def test_unknown_alias_returns_none(taxonomy: SkillTaxonomy) -> None:
    assert taxonomy.resolve("ruby") is None
    assert taxonomy.resolve("") is None
    assert taxonomy.resolve(None) is None


def test_duplicate_canonical_name_raises(tmp_path: Path) -> None:
    payload_path = tmp_path / "bad_taxonomy.json"
    payload_path.write_text(
        """
        {
          "version": "1.0",
          "skills": [
            {"canonical_name": "Python", "category": "programming_language", "aliases": []},
            {"canonical_name": "Python", "category": "programming_language", "aliases": []}
          ]
        }
        """,
        encoding="utf-8",
    )

    with pytest.raises(TaxonomyError, match="Duplicate canonical_name"):
        SkillTaxonomy.from_path(payload_path)


def test_conflicting_alias_raises(tmp_path: Path) -> None:
    payload_path = tmp_path / "bad_alias_taxonomy.json"
    payload_path.write_text(
        """
        {
          "version": "1.0",
          "skills": [
            {"canonical_name": "Python", "category": "programming_language", "aliases": ["py"]},
            {"canonical_name": "PyTorch", "category": "ml_library", "aliases": ["py"]}
          ]
        }
        """,
        encoding="utf-8",
    )

    with pytest.raises(TaxonomyError, match="Alias 'py'"):
        SkillTaxonomy.from_path(payload_path)
