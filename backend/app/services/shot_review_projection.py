"""Review-safe projection of shot reference media and bound story entities."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def _rows(values: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for value in values if isinstance(values, list) else []:
        if isinstance(value, str):
            entity_id, name = "", value.strip()
        elif isinstance(value, Mapping):
            entity_id = str(
                value.get("entity_id")
                or value.get("canonical_entity_id")
                or value.get("character_id")
                or value.get("id")
                or ""
            ).strip()
            name = str(value.get("name") or value.get("entity_name") or "").strip()
        else:
            continue
        if not name:
            continue
        key = entity_id or name
        if key in seen:
            continue
        seen.add(key)
        rows.append({"id": entity_id, "name": name})
    return rows


def _first_non_empty_groups(groups: Iterable[Any]) -> list[dict[str, str]]:
    for group in groups:
        rows = _rows(group)
        if rows:
            return rows
    return []


def shot_reference_review_fields(
    shot: Any,
    *,
    latest_video: Any = None,
    video_extra: Mapping[str, Any] | None = None,
    fallback_character_names: Iterable[str] = (),
) -> dict[str, Any]:
    """Return stable preview media and minimal, non-sensitive entity labels."""
    video_extra = video_extra or {}
    shot_extra = shot.extra_data if isinstance(getattr(shot, "extra_data", None), dict) else {}
    entity_refs = shot_extra.get("entity_refs") if isinstance(shot_extra.get("entity_refs"), dict) else {}
    characters = _first_non_empty_groups((
        video_extra.get("character_refs"),
        entity_refs.get("characters"),
        getattr(shot, "character_refs", None),
        list(fallback_character_names),
    ))
    reference_image_url = (
        getattr(shot, "image_url", None)
        or getattr(latest_video, "image_url", None)
        or video_extra.get("reference_image")
    )
    return {
        "character_names": [item["name"] for item in characters],
        "reference_image_url": reference_image_url,
        "reference_image_status": getattr(shot, "image_status", None),
        "reference_asset_id": getattr(shot, "image_asset_id", None),
        "reference_entities": {
            "characters": characters,
            "scenes": _first_non_empty_groups((video_extra.get("scene_refs"), entity_refs.get("scenes"))),
            "props": _first_non_empty_groups((video_extra.get("prop_refs"), entity_refs.get("props"))),
        },
    }


__all__ = ["shot_reference_review_fields"]
