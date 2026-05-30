"""Shot quality and budget estimation helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.model_registry import get_task_default
from app.services.ai_generation_feedback import build_ai_generation_feedback


def _has_text(value: Optional[str]) -> bool:
    return bool(value and str(value).strip())


def _names_from_refs(refs: Any) -> List[str]:
    if not isinstance(refs, list):
        return []
    names: List[str] = []
    for item in refs:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("character_name") or item.get("title") or "").strip()
        else:
            name = str(item or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def estimate_shot_generation_budget(shot: Any) -> Dict[str, Any]:
    duration = int(getattr(shot, "duration", 4) or 4)
    dialogue = getattr(shot, "dialogue", None) or ""
    prompt = getattr(shot, "prompt", None) or ""
    visual_description = getattr(shot, "visual_description", None) or ""
    subtitle_text = (((getattr(shot, "extra_data", None) or {}).get("subtitle_text")) if isinstance(getattr(shot, "extra_data", None), dict) else None) or dialogue
    shot_video_default = get_task_default("shot_video") or {}
    shot_audio_video_default = get_task_default("shot_audio_video") or {}

    video_capabilities = shot_video_default.get("default_model", {}).get("capabilities", [])
    av_capabilities = shot_audio_video_default.get("default_model", {}).get("capabilities", [])

    prompt_tokens = max(16, len(prompt) // 2 + len(visual_description) // 2 + len(dialogue) // 2)
    subtitle_tokens = max(0, len(subtitle_text) // 2)
    total_tokens = prompt_tokens + subtitle_tokens

    return {
        "estimated_duration_seconds": duration,
        "estimated_prompt_tokens": prompt_tokens,
        "estimated_subtitle_tokens": subtitle_tokens,
        "estimated_total_tokens": total_tokens,
        "estimated_video_task": {
            "task_type": "shot_video",
            "default_model_id": shot_video_default.get("default_model_id"),
            "capabilities": video_capabilities,
        },
        "estimated_direct_av_task": {
            "task_type": "shot_audio_video",
            "default_model_id": shot_audio_video_default.get("default_model_id"),
            "capabilities": av_capabilities,
        },
        "estimated_cost_notes": [
            "实际费用由所选模型和供应商决定",
            "当前估算仅用于提示镜头复杂度和模型选择",
        ],
    }


def build_shot_quality_report(shot: Any) -> Dict[str, Any]:
    extra_data = getattr(shot, "extra_data", None) if isinstance(getattr(shot, "extra_data", None), dict) else {}
    warnings: List[str] = []
    blockers: List[str] = []
    suggestions: List[str] = []

    if not _has_text(getattr(shot, "prompt", None)) and not _has_text(getattr(shot, "visual_description", None)):
        blockers.append("缺少视频提示词和视觉描述，无法稳定生成镜头视频")
    if not _has_text(getattr(shot, "dialogue", None)) and not _has_text(extra_data.get("subtitle_text")):
        warnings.append("当前镜头没有台词或字幕文本，生成后可能没有对白轨")

    keyframes = getattr(shot, "keyframes", None) or []
    if not isinstance(keyframes, list) or len(keyframes) == 0:
        warnings.append("未设置关键帧，长镜头一致性可能较弱")
        suggestions.append("为镜头补充 start/end/keyframe 参考")

    character_refs = getattr(shot, "character_refs", None) or []
    if not isinstance(character_refs, list) or len(character_refs) == 0:
        warnings.append("未显式绑定角色引用，可能退化为通用角色生成")

    entity_refs = extra_data.get("entity_refs") if isinstance(extra_data.get("entity_refs"), dict) else {}
    if not _names_from_refs(entity_refs.get("scenes")):
        warnings.append("缺少场景引用，场景一致性较弱")
    if not _names_from_refs(entity_refs.get("props")):
        warnings.append("缺少道具引用，道具状态可能不一致")
    if not _names_from_refs(entity_refs.get("events")):
        warnings.append("缺少事件引用，镜头与小说事件的衔接可能偏弱")

    production_context = extra_data.get("production_context") if isinstance(extra_data.get("production_context"), dict) else {}
    review_state = production_context.get("review_state") or extra_data.get("review_state") or "pending_review"
    if review_state not in {"approved", "locked"}:
        suggestions.append("完成镜头审核后再进入批量生成或真实渲染")

    score = 100
    score -= 20 if blockers else 0
    score -= min(35, len(warnings) * 6)
    score = max(0, score)

    return {
        "score": score,
        "status": "blocked" if blockers else ("warning" if warnings else "ready"),
        "blockers": blockers,
        "warnings": warnings,
        "suggestions": suggestions,
        "summary": build_ai_generation_feedback(
            stage="shot_quality_check",
            message="镜头质量检查完成",
            context={
                "novel_id": extra_data.get("novel_id"),
                "chapter_id": extra_data.get("chapter_id"),
                "title": getattr(shot, "prompt", None) or getattr(shot, "visual_description", None),
                "characters": getattr(shot, "character_refs", None) or [],
                "scenes": entity_refs.get("scenes") or [],
                "props": entity_refs.get("props") or [],
                "events": entity_refs.get("events") or [],
            },
            warnings=warnings,
            extra={
                "score": score,
                "status": "blocked" if blockers else ("warning" if warnings else "ready"),
            },
        ),
    }
