from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SeriesStageSkillMissing(ValueError):
    """A required automatic-production stage has no published Prompt Skill."""


@dataclass(frozen=True)
class BoundSeriesStageSkill:
    rendered_prompt: str
    evidence: dict[str, Any]
