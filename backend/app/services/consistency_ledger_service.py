from __future__ import annotations

from typing import Any, Dict, List


def _json_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _shot_character_refs(shot: Dict[str, Any]) -> List[Any]:
    refs = _json_list(shot.get("character_refs"))
    entity_refs = _json_dict(shot.get("entity_refs"))
    return [
        *refs,
        *_json_list(entity_refs.get("character")),
        *_json_list(entity_refs.get("characters")),
    ]


def build_consistency_ledger(
    shots: List[Dict[str, Any]],
    episode_contract: Dict[str, Any],
    jobs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    locked_characters = [
        item
        for item in _json_list(episode_contract.get("entity_locks"))
        if _json_dict(item).get("entity_type") == "character"
    ]

    for shot in shots:
        if locked_characters and not _shot_character_refs(shot):
            findings.append(
                {
                    "code": "shot_character_unbound",
                    "severity": "blocking",
                    "shot_id": shot.get("id"),
                    "message": "镜头没有绑定角色参考，人物一致性不可控",
                    "repair_action": {
                        "code": "bind_character_reference",
                        "label": "绑定角色参考",
                        "risk": "navigation",
                    },
                }
            )

    blocking_count = len([item for item in findings if item.get("severity") == "blocking"])
    score = max(0, 100 - blocking_count * 25 - len(findings) * 5)
    return {
        "overall_score": score,
        "dimensions": {
            "style": 100,
            "character_visual": 0 if blocking_count else 100,
            "scene": 100,
            "prop_state": 100,
            "voice": 100,
            "event_continuity": 100,
            "subtitle_timing": 100,
        },
        "findings": findings,
    }
