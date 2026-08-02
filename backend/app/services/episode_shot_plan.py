"""Resolve storyboard shot plans and canonical scene-owned dialogue."""

from __future__ import annotations

from typing import Any

from app.models import Storyboard


def planned_shots(storyboard: Storyboard) -> list[dict[str, Any]]:
    content = storyboard.content if isinstance(storyboard.content, dict) else {}
    shots = [dict(item) for item in (content.get("shots") or []) if isinstance(item, dict)]
    try:
        expected = max(1, int(content.get("planned_shot_count") or len(shots) or 1))
    except (TypeError, ValueError):
        expected = max(1, len(shots))
    while len(shots) < expected:
        number = len(shots) + 1
        shots.append({
            "shot_number": number,
            "prompt": f"{storyboard.title}，镜头{number}，保持人物、场景与道具连续",
            "visual_description": str(content.get("source_text") or storyboard.description or ""),
            "dialogue": None,
        })
    return shots[:expected]


def dialogue_lines_by_storyboard(
    dialogue_lines: list[dict[str, Any]], storyboards: list[Storyboard],
) -> dict[str, list[dict[str, Any]]]:
    """Bind each canonical dialogue to one scene; ambiguous matches fail closed."""
    assigned = {str(board.id): [] for board in storyboards}
    if len(storyboards) == 1:
        assigned[str(storyboards[0].id)] = list(dialogue_lines)
        return assigned
    sources = {
        str(board.id): str((board.content or {}).get("source_text") or "")
        for board in storyboards
    }
    for line in dialogue_lines:
        spoken = str(line.get("spoken_text") or "").strip()
        matches = [board_id for board_id, source in sources.items() if spoken and spoken in source]
        if len(matches) == 1:
            assigned[matches[0]].append(line)
    return assigned


def dialogue_source_evidence(
    script_id: str, line: dict[str, Any], scene_index: Any,
) -> dict[str, Any]:
    return {
        "script_id": script_id, "source_span": line.get("source_span"),
        "binding_rule": "scene_text_unique_v1", "scene_index": scene_index,
    }


__all__ = ["dialogue_lines_by_storyboard", "dialogue_source_evidence", "planned_shots"]
