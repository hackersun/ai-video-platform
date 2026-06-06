"""Normalize StoryEntity references across generation services."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


ENTITY_REF_KEYS: Dict[str, str] = {
    "characters": "character",
    "scenes": "scene",
    "props": "prop",
    "events": "event",
}


def _compact(values: Iterable[Optional[str]]) -> List[str]:
    seen: dict[str, None] = {}
    for value in values:
        if value and value not in seen:
            seen[value] = None
    return list(seen.keys())


def _normalize_single_ref(value: Any, entity_type: str) -> Optional[Dict[str, Any]]:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        return {"entity_id": stripped, "entity_type": entity_type}

    if not isinstance(value, dict):
        return None

    ref = dict(value)
    entity_id = (
        ref.get("entity_id")
        or ref.get("id")
        or ref.get("story_entity_id")
    )
    if entity_id:
        ref["entity_id"] = str(entity_id)
    ref.setdefault("entity_type", entity_type)
    return ref if ref.get("entity_id") or ref.get("name") else None


def normalize_entity_refs(value: Any) -> Dict[str, List[Dict[str, Any]]]:
    """Return canonical entity_refs with dict entries for every group.

    Legacy code wrote lists of IDs, while newer code writes full dict refs.
    This helper accepts both and always returns:
    {"characters": [{"entity_id": "...", "entity_type": "character"}], ...}
    """
    source = value if isinstance(value, dict) else {}
    normalized: Dict[str, List[Dict[str, Any]]] = {}
    for key, entity_type in ENTITY_REF_KEYS.items():
        refs = source.get(key)
        if not isinstance(refs, list):
            refs = []
        entries = []
        seen: set[str] = set()
        for item in refs:
            ref = _normalize_single_ref(item, entity_type)
            if not ref:
                continue
            dedupe_key = str(ref.get("entity_id") or ref.get("name") or "")
            if dedupe_key and dedupe_key in seen:
                continue
            if dedupe_key:
                seen.add(dedupe_key)
            entries.append(ref)
        normalized[key] = entries
    return normalized


def entity_ref_ids(entity_refs: Any, key: str) -> List[str]:
    """Extract stable entity IDs from canonical or legacy refs."""
    normalized = normalize_entity_refs(entity_refs)
    return _compact(str(ref.get("entity_id")) for ref in normalized.get(key, []) if ref.get("entity_id"))
