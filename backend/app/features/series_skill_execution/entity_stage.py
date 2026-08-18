"""Model-first candidate selection kept outside the legacy entity hotspot."""

from __future__ import annotations

from hashlib import sha256
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from .model_pipeline import execute_skill_model_or_fallback
from .stage_contracts import validate_entity_candidates


def build_entity_stage_input(
    *, source_type: str, source_text: str, requested_types: set[str],
) -> str:
    """Build the non-optional source payload for entity model execution."""
    allowed_types = "、".join(sorted(requested_types))
    return (
        "请从下方原文抽取动漫制作需要长期保持一致的实体。\n"
        f"来源类型：{source_type}\n"
        f"允许类型：{allowed_types}\n"
        "每项必须包含 entity_type、name、evidence、confidence；"
        "evidence 必须是原文中的连续片段。\n"
        "不要把动作短语、身体部位、情绪、时间或地点残片当作实体。\n"
        "只输出 JSON 数组，不要输出解释或 Markdown。\n\n"
        f"【原文】\n{(source_text or '')[:30000]}"
    )


def _merge_deterministic_entities(
    model_items: list[dict[str, Any]], deterministic_items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Keep model semantics while making explicit source facts authoritative."""
    merged = [dict(item) for item in model_items]
    indexes = {
        (str(item.get("entity_type") or ""), str(item.get("name") or "")): index
        for index, item in enumerate(merged)
    }
    merged_count = 0
    for deterministic in deterministic_items:
        key = (str(deterministic.get("entity_type") or ""), str(deterministic.get("name") or ""))
        if key not in indexes:
            continue
        index = indexes[key]
        current = merged[index]
        deterministic_attributes = dict(deterministic.get("attributes") or {})
        current_attributes = dict(current.get("attributes") or {})
        visual_dna = {
            **dict(current_attributes.get("visual_dna") or {}),
            **dict(deterministic_attributes.get("visual_dna") or {}),
        }
        merged[index] = {
            **deterministic,
            **current,
            "attributes": {**current_attributes, **deterministic_attributes, "visual_dna": visual_dna},
        }
        merged_count += 1
    return merged, {"merged_entities": merged_count, "added_entities": 0}


async def resolve_entity_candidates(
    db: AsyncSession, *, user_id: str, rendered_prompt: str, source_text: str,
    requested_types: set[str], supplied: list[dict[str, Any]] | None,
    fallback: Callable[[], list[dict[str, Any]]], model_config_id: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if supplied is not None:
        values = [dict(item) for item in supplied if item.get("entity_type") in requested_types]
        return values, {
            "execution_mode": "supplied_candidates", "validation_status": "caller_owned",
            "fallback_reason": None,
            "input_sha256": sha256(rendered_prompt.encode("utf-8")).hexdigest(),
        }
    result = await execute_skill_model_or_fallback(
        db, user_id=user_id, rendered_prompt=rendered_prompt, output_contract="json_array",
        validator=lambda value: validate_entity_candidates(
            value, source_text=source_text, requested_types=requested_types,
        ), fallback=fallback, explicit_config_id=model_config_id,
    )
    if result.evidence.get("execution_mode") != "provider_model":
        return result.value, result.evidence
    values, enrichment = _merge_deterministic_entities(result.value, fallback())
    return values, {**result.evidence, "deterministic_enrichment": enrichment}


__all__ = ["build_entity_stage_input", "resolve_entity_candidates"]
