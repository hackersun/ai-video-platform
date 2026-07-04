from __future__ import annotations

from typing import Any, Dict

from app.core.model_registry import get_model_reference_limits


STRICT_REFERENCE_BLOCKING_REASON = "严格一致模式需要支持参考图输入的图像模型"


def _limits_for(model_id: str, override: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if override is not None:
        return dict(override)
    return get_model_reference_limits(model_id)


def decide_asset_generation_strategy(
    *,
    consistency_mode: str,
    provider_name: str,
    model_id: str,
    entity_type: str,
    has_anchor: bool,
    model_limits: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    mode = (consistency_mode or "off").strip().lower()
    limits = _limits_for(model_id, model_limits)
    image_capacity = int(limits.get("images", 0) or 0)
    supports_at_reference = bool(limits.get("at_reference", False))
    can_send_reference = has_anchor and image_capacity > 0

    base_strategy: Dict[str, Any] = {
        "consistency_mode": mode,
        "provider_name": provider_name,
        "model_id": model_id,
        "entity_type": entity_type,
        "has_anchor": has_anchor,
        "strict_blocking": False,
        "warnings": [],
        "model_limits": limits,
    }

    if mode == "off":
        return {**base_strategy, "mode": "text_prompt"}

    if mode == "draft":
        return {
            **base_strategy,
            "mode": "text_contract",
            "warnings": ["草稿模式允许文本契约生成，资产需人工复审后再定稿。"],
        }

    if mode == "strict" and has_anchor and not can_send_reference:
        return {
            **base_strategy,
            "mode": "blocked",
            "strict_blocking": True,
            "blocking_reason": STRICT_REFERENCE_BLOCKING_REASON,
        }

    if can_send_reference:
        return {
            **base_strategy,
            "mode": "reference_image_contract",
            "supports_at_reference": supports_at_reference,
        }

    return {
        **base_strategy,
        "mode": "text_contract",
        "warnings": ["当前模型的参考图不会作为模型输入，将仅使用小说视觉契约和文字约束。"],
    }
