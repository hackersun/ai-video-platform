"""Deterministic cross-episode anchor recommendations for a series run."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable


DIMENSIONS = (
    "narrative_truth",
    "character_visual",
    "scene_prop_state",
    "style_cinematography",
    "voice_dialogue",
    "delivery_integrity",
)

ANCHOR_MODE_CONTRACTS = {
    "smoke": {"target_count": 2, "required_episodes": 2},
    "representative": {"target_count": 3, "required_episodes": 3},
    "full": {"target_count": 6, "required_episodes": 4},
}


@dataclass(frozen=True)
class AnchorShotInput:
    id: str
    episode_number: int
    shot_number: int
    prompt: str
    visual_description: str
    dialogue: str
    character_refs: tuple[Any, ...]
    camera_angle: str | None
    camera_movement: str | None
    lighting: str | None
    color_grading: str | None
    video_url: str | None
    audio_url: str | None
    video_status: str | None
    audio_status: str | None
    extra_data: dict[str, Any]


def anchor_shot_input(shot: Any, *, episode_number: int) -> AnchorShotInput:
    """Copy recommendation evidence without dirtying the canonical ORM shot."""
    return AnchorShotInput(
        id=str(shot.id), episode_number=episode_number,
        shot_number=int(getattr(shot, "shot_number", 0) or 0),
        prompt=str(getattr(shot, "prompt", "") or ""),
        visual_description=str(getattr(shot, "visual_description", "") or ""),
        dialogue=str(getattr(shot, "dialogue", "") or ""),
        character_refs=tuple(getattr(shot, "character_refs", None) or ()),
        camera_angle=getattr(shot, "camera_angle", None), camera_movement=getattr(shot, "camera_movement", None),
        lighting=getattr(shot, "lighting", None), color_grading=getattr(shot, "color_grading", None),
        video_url=getattr(shot, "video_url", None), audio_url=getattr(shot, "audio_url", None),
        video_status=getattr(shot, "video_status", None), audio_status=getattr(shot, "audio_status", None),
        extra_data=dict(getattr(shot, "extra_data", None) or {}),
    )


def _episode_number(shot: Any) -> int:
    return int(getattr(shot, "episode_number", 0) or (getattr(shot, "extra_data", None) or {}).get("episode_number") or 0)


def _dimensions(shot: Any) -> list[str]:
    text = " ".join(str(value or "") for value in (
        getattr(shot, "prompt", ""), getattr(shot, "visual_description", ""), getattr(shot, "dialogue", "")
    )).lower()
    extra = getattr(shot, "extra_data", None) or {}
    result: set[str] = set()
    if getattr(shot, "character_refs", None) or extra.get("character_evidence") or any(key in text for key in ("主角", "角色", "登场")):
        result.add("character_visual")
    if extra.get("continuity_prop") or extra.get("scene_refs") or extra.get("prop_refs") or any(key in text for key in ("场景", "道具", "新场景")):
        result.add("scene_prop_state")
    if extra.get("event_refs") or extra.get("final_consequence") or any(key in text for key in ("转折", "决战", "后果", "事件")):
        result.add("narrative_truth")
    if str(getattr(shot, "dialogue", "") or "").strip():
        result.add("voice_dialogue")
    if extra.get("style_evidence") or any(getattr(shot, key, None) for key in ("camera_angle", "camera_movement", "lighting", "color_grading")):
        result.add("style_cinematography")
    artifact_ready = getattr(shot, "video_status", None) in {"succeeded", "completed"} and bool(getattr(shot, "video_url", None))
    has_final_consequence = extra.get("final_consequence") or any(key in text for key in ("最终", "结局", "后果", "因此", "永久"))
    if extra.get("delivery_evidence") or artifact_ready or has_final_consequence:
        result.add("delivery_integrity")
    return [item for item in DIMENSIONS if item in result]


def _character_keys(shot: Any) -> set[str]:
    keys = set()
    for ref in getattr(shot, "character_refs", None) or ():
        if isinstance(ref, dict):
            value = ref.get("character_id") or ref.get("name")
            if value:
                keys.add(str(value))
    return keys


def _signals(shot: Any, recurring_characters: set[str]) -> list[str]:
    extra = getattr(shot, "extra_data", None) or {}
    text = " ".join(str(value or "") for value in (getattr(shot, "prompt", ""), getattr(shot, "visual_description", ""))).lower()
    signals = []
    if extra.get("first_protagonist_appearance") or "首次登场" in text:
        signals.append("first_protagonist_appearance")
    if extra.get("recurring_character") or _character_keys(shot).intersection(recurring_characters):
        signals.append("recurring_character")
    if extra.get("scene_change") or any(key in text for key in ("新场景", "转场", "进入")):
        signals.append("major_scene_change")
    if extra.get("continuity_prop") or extra.get("prop_refs"):
        signals.append("continuity_prop")
    if extra.get("event_turning_point") or extra.get("event_refs") or any(key in text for key in ("转折", "反转", "决战")):
        signals.append("event_turning_point")
    if str(getattr(shot, "dialogue", "") or "").strip():
        signals.append("dialogue_voice")
    if extra.get("final_consequence") or any(key in text for key in ("最终", "结局", "后果", "因此", "永久")):
        signals.append("final_consequence")
    return signals


def _score(shot: Any, recurring_characters: set[str]) -> tuple[int, int, int, str]:
    dimensions = _dimensions(shot)
    return (-len(_signals(shot, recurring_characters)), -len(dimensions), int(getattr(shot, "shot_number", 0) or 0), str(shot.id))


def recommend_anchor_shots(shots: Iterable[Any], *, mode: str = "smoke") -> list[dict[str, Any]]:
    if mode not in ANCHOR_MODE_CONTRACTS:
        raise ValueError("anchor mode must be smoke, representative or full")
    shot_list = list(shots)
    character_counts: dict[str, int] = defaultdict(int)
    for shot in shot_list:
        for key in _character_keys(shot):
            character_counts[key] += 1
    recurring_characters = {key for key, count in character_counts.items() if count > 1}
    grouped: dict[int, list[Any]] = defaultdict(list)
    for shot in shot_list:
        episode = _episode_number(shot)
        if episode > 0:
            grouped[episode].append(shot)
    ordered_episodes = sorted(grouped)
    target = ANCHOR_MODE_CONTRACTS[mode]["target_count"]
    selected: list[Any] = []
    if mode == "smoke" and len(ordered_episodes) > 1:
        primary_episodes = [ordered_episodes[0], ordered_episodes[-1]]
    elif mode == "representative" and len(ordered_episodes) > 2:
        primary_episodes = [ordered_episodes[0], ordered_episodes[len(ordered_episodes) // 2], ordered_episodes[-1]]
    else:
        primary_episodes = ordered_episodes
    for episode in primary_episodes:
        selected.append(sorted(grouped[episode], key=lambda shot: _score(shot, recurring_characters))[0])
        if mode in {"smoke", "representative"} and len(selected) == target:
            break
    remaining = [shot for episode in ordered_episodes for shot in grouped[episode] if shot not in selected]
    selected.extend(sorted(remaining, key=lambda shot: _score(shot, recurring_characters))[: max(0, target - len(selected))])
    return [
        {
            "shot_id": str(shot.id),
            "episode_number": _episode_number(shot),
            "shot_number": int(getattr(shot, "shot_number", 0) or 0),
            "dimensions": _dimensions(shot),
            "signals": _signals(shot, recurring_characters),
            "reason": "、".join(_signals(shot, recurring_characters) or _dimensions(shot)),
        }
        for shot in selected[:target]
    ]


def validate_anchor_selection(selected_ids: Iterable[str], allowed_ids: set[str]) -> list[str]:
    selected = list(dict.fromkeys(str(item) for item in selected_ids if str(item).strip()))
    if not selected:
        raise ValueError("select at least one anchor shot")
    if any(item not in allowed_ids for item in selected):
        raise ValueError("selected shot is outside series run")
    return selected


def anchor_coverage_blocker(recommendations: list[dict[str, Any]], *, mode: str) -> dict[str, Any] | None:
    if mode not in ANCHOR_MODE_CONTRACTS:
        raise ValueError("anchor mode must be smoke, representative or full")
    required_count = ANCHOR_MODE_CONTRACTS[mode]["target_count"]
    required_episodes = ANCHOR_MODE_CONTRACTS[mode]["required_episodes"]
    covered_episodes = {item["episode_number"] for item in recommendations}
    covered_dimensions = set().union(*(set(item["dimensions"]) for item in recommendations)) if recommendations else set()
    dimensions_missing = [item for item in DIMENSIONS if item not in covered_dimensions] if mode == "full" else []
    if len(recommendations) >= required_count and len(covered_episodes) >= required_episodes and not dimensions_missing:
        return None
    return {
        "code": "insufficient_anchor_coverage",
        "mode": mode,
        "message": f"{mode} 验证需要 {required_count} 个镜头覆盖 {required_episodes} 章",
        "available_count": len(recommendations),
        "covered_episode_count": len(covered_episodes),
        "missing_dimensions": dimensions_missing,
    }


__all__ = ["ANCHOR_MODE_CONTRACTS", "AnchorShotInput", "DIMENSIONS", "anchor_shot_input", "recommend_anchor_shots", "validate_anchor_selection", "anchor_coverage_blocker"]
