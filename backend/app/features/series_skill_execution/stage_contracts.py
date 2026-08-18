"""Deterministic admission contracts for model-generated series artifacts."""

from __future__ import annotations

import json
from typing import Any


ENTITY_TYPES = frozenset({"character", "scene", "prop", "event"})
EVENT_FIELDS = ("actor", "action", "object", "outcome")


def _normalize_confidence(value: Any) -> int:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 80
    if 0 <= score <= 1:
        score *= 100
    return max(0, min(100, round(score)))


def validate_entity_candidates(
    value: Any, *, source_text: str, requested_types: set[str],
) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = value.get("entities")
    if not isinstance(value, list):
        raise ValueError("entity_array_required")
    accepted: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        entity_type = str(raw.get("entity_type") or raw.get("type") or "").strip()
        name = str(raw.get("name") or raw.get("title") or "").strip()
        evidence = str(raw.get("evidence") or "").strip()
        if entity_type not in ENTITY_TYPES or entity_type not in requested_types:
            continue
        if not name or (name not in source_text and evidence not in source_text):
            continue
        if entity_type == "event" and not all(str(raw.get(field) or "").strip() for field in EVENT_FIELDS):
            continue
        accepted.append({
            **raw, "entity_type": entity_type, "name": name[:200],
            "description": raw.get("description") or evidence,
            "aliases": raw.get("aliases") if isinstance(raw.get("aliases"), list) else [],
            "attributes": raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {},
            "evidence": evidence or name, "confidence": _normalize_confidence(raw.get("confidence")),
            "source": "provider_model",
        })
    if not accepted:
        raise ValueError("entity_candidates_rejected")
    return accepted


def validate_script(value: Any, *, required_dialogues: list[str] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("script_object_required")
    content = str(value.get("content") or value.get("screenplay") or "").strip()
    scenes = value.get("scenes")
    if not content and not isinstance(scenes, list):
        raise ValueError("script_content_required")
    serialized = json.dumps(value, ensure_ascii=False)
    if any(dialogue and dialogue not in serialized for dialogue in (required_dialogues or [])):
        raise ValueError("script_dialogue_mismatch")
    return {**value, "content": content}


def validate_storyboard(value: Any, *, required_dialogue: str | None = None) -> dict[str, Any]:
    shots = value.get("shots") if isinstance(value, dict) else value
    if not isinstance(shots, list) or not shots:
        raise ValueError("storyboard_shots_required")
    admitted = [item for item in shots if isinstance(item, dict) and (
        str(item.get("visual_description") or item.get("prompt") or "").strip()
    )]
    if not admitted:
        raise ValueError("storyboard_shots_rejected")
    if required_dialogue and required_dialogue not in json.dumps(admitted, ensure_ascii=False):
        raise ValueError("storyboard_dialogue_mismatch")
    return {"shots": admitted}


def validate_shot(value: Any, *, required_dialogue: str | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("shot_object_required")
    prompt = str(value.get("prompt") or value.get("visual_description") or "").strip()
    if not prompt:
        raise ValueError("shot_prompt_required")
    dialogue = str(value.get("dialogue") or "").strip() or None
    if required_dialogue and dialogue != required_dialogue:
        raise ValueError("shot_dialogue_mismatch")
    return {
        "prompt": prompt,
        "visual_description": str(value.get("visual_description") or prompt).strip(),
        "dialogue": dialogue,
    }


__all__ = ["validate_entity_candidates", "validate_script", "validate_shot", "validate_storyboard"]
