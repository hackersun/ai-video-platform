"""Pure workflow state transitions for media generation."""

from typing import Iterable, Optional


def complete_steps(existing: Optional[Iterable[int]], *steps: int) -> list[int]:
    values = list(existing or [])
    for step in steps:
        if step not in values:
            values.append(step)
    return sorted(values)
