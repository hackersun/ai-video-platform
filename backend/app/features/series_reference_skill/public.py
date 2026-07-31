"""Public series-reference Prompt Skill binding."""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.series_skill_execution.public import BoundSeriesStageSkill, bind_series_stage_skill
from app.services.reference_layout_evaluator import reference_layout_prompt_instruction


def _image_route(run: Any) -> tuple[str | None, str | None]:
    image = (((run.model_bindings or {}).get("capabilities") or {}).get("image") or {})
    return image.get("provider_id") or image.get("provider_name"), image.get("api_model_id")


def character_visual_contract(characters: Sequence[Any]) -> str:
    """Render canonical character DNA as provider-visible hard constraints."""
    lines: list[str] = []
    for character in characters:
        name = str(getattr(character, "canonical_name", None) or getattr(character, "name", "")).strip()
        appearance = str(getattr(character, "appearance", None) or "").strip()
        attributes = getattr(character, "attributes", None)
        dna = (attributes if isinstance(attributes, dict) else {}).get("visual_dna") or {}
        details = [
            f"{('服装' if key == 'costume' else key)}={value}"
            for key, value in dna.items() if str(value or "").strip()
        ]
        if appearance:
            details.insert(0, f"外观定稿={appearance.rstrip('。')}")
        lines.append(f"角色{name}的不可变视觉DNA：{'、'.join(details) or '未完整锁定'}。")
    return "".join(lines) + (
        "服装必须逐项复现锁定的颜色、材质、长度、领型、门襟、扣件和配饰；"
        "不得改成短衫、制服、夹克或其他版型，不得省略外套。"
    )


async def bind_series_reference_skill(
    db: AsyncSession, *, run: Any, bible: Any, characters: Sequence[Any], asset_id: str,
) -> BoundSeriesStageSkill:
    names = "、".join(dict.fromkeys(
        str(getattr(item, "canonical_name", None) or getattr(item, "name", "")).strip()
        for item in characters
        if str(getattr(item, "canonical_name", None) or getattr(item, "name", "")).strip()
    ))
    layout = reference_layout_prompt_instruction().strip()
    visual_contract = character_visual_contract(characters)
    provider_name, model_id = _image_route(run)
    internal_prompt = (
        f"为《{bible.title}》制作一张单一复合设定板，完整包含角色 {names} 与全局风格规范。"
        f"{visual_contract}{layout}禁止拆成多个文件，禁止文字水印。"
    )
    return await bind_series_stage_skill(
        db, user_id=run.user_id, task="series_reference_board", stage="asset",
        context={"characters": names, "style": bible.style, "layout": layout, "visual_contract": visual_contract},
        internal_prompt=internal_prompt, artifact_type="asset", artifact_id=asset_id,
        execution_mode="provider_model", provider_name=provider_name, model_id=model_id,
    )


__all__ = ["bind_series_reference_skill", "character_visual_contract"]
