from __future__ import annotations

from typing import Any, Dict, List

from app.services.studio_guidance import QUALITY_DIMENSIONS


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
    quality_evaluation: Dict[str, Any] | None = None,
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
    evaluation = _json_dict(quality_evaluation)
    evaluated_dimensions = [str(item) for item in _json_list(evaluation.get("dimensions"))]
    evaluation_ids = _json_list(evaluation.get("evaluation_ids"))
    has_partial_evaluation = evaluation.get("score") is not None or bool(evaluated_dimensions)
    has_complete_evaluation = (
        set(evaluated_dimensions) == QUALITY_DIMENSIONS
        and len(evaluation_ids) == len(QUALITY_DIMENSIONS)
        and evaluation.get("score") is not None
        and bool(evaluation.get("artifact_id"))
    )
    evaluation_status = "evaluated" if has_complete_evaluation else "partial" if has_partial_evaluation else "not_evaluated"
    return {
        "evaluation_status": evaluation_status,
        "preflight_status": "blocked" if blocking_count else "ready",
        "overall_score": float(evaluation["score"]) if has_complete_evaluation else None,
        "dimensions": {},
        "evaluated_dimensions": evaluated_dimensions,
        "findings": findings,
    }
