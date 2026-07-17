"""Story entity statistics shared by review-facing endpoints."""

from collections.abc import Iterable

from app.services.story_entity_lifecycle import is_entity_production_visible


def production_entity_counts(entities: Iterable, entity_types: Iterable[str]) -> dict:
    counts = {entity_type: 0 for entity_type in sorted(entity_types)}
    for entity in entities:
        counts[str(entity.entity_type)] += int(is_entity_production_visible(entity))
    return {"total": sum(counts.values()), "counts": counts}
