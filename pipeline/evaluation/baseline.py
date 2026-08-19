"""Simple frequency baseline model for comparison with the z-score trend model."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class BaselineSkillScore:
    """Skill score using only raw frequency in the latest period."""

    skill: str
    current_mentions: int


class FrequencyBaseline:
    """Rank skills by raw mention count in the current (last) period."""

    name: str = "frequency_baseline"

    def compute(
        self,
        weekly_counts: Sequence[Mapping[str, int]],
    ) -> list[BaselineSkillScore]:
        if not weekly_counts:
            return []

        current = dict(weekly_counts[-1])
        all_skills: set[str] = set()
        for period in weekly_counts:
            all_skills.update(period.keys())

        scores = [
            BaselineSkillScore(
                skill=skill,
                current_mentions=int(current.get(skill, 0)),
            )
            for skill in all_skills
        ]
        scores.sort(key=lambda item: (-item.current_mentions, item.skill))
        return scores
