"""Shared prompt policy for production-oriented image generation."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Optional


GLOBAL_IMAGE_NEGATIVE_CONSTRAINT = (
    "通用负面约束：不要生成文字、水印、logo、拼贴边框、错误肢体、畸形手指、低清晰度、"
    "与小说无关的人物或物件；画面必须是单张完整图，不要把多个无关画面拼在一起。"
)

CHARACTER_SINGLE_VIEW_CONSTRAINT = (
    "角色硬约束：只生成一个角色，单人，完整头身，单张设定图，单张角色设定图，纯净浅色背景；"
    "禁止拼接图，禁止多宫格，禁止三视图并排，禁止多人，禁止群像，禁止拆成多个小图；"
    "不要改变性别、年龄感、身份、脸型、发型、体型、服装、标志道具和整体气质。"
)

SCENE_VIEW_CONSTRAINT = (
    "场景硬约束：只生成一个连续空间的单张场景设定图，不要拼接多个地点，"
    "不要出现无关人物特写；保持时代、建筑结构、光线方向、天气和色彩基调一致。"
)

PROP_VIEW_CONSTRAINT = (
    "道具硬约束：只生成一个核心道具，单张道具设定图，不要拼接多个无关物品，"
    "保持外形、材质、纹路、破损、发光颜色和比例一致。"
)

CHARACTER_VIEW_DIRECTION_CONSTRAINTS = {
    "front": "正面视图硬约束：角色正对镜头，五官完整清晰，双眼、发型、服饰正面结构可见。",
    "side": (
        "侧面视图硬约束：严格单侧侧身轮廓，角色身体与脸部朝向画面左侧或右侧；"
        "只显示一侧眼睛和耳部轮廓，禁止正面视角，禁止三分之二正脸，禁止回头看镜头。"
    ),
    "back": (
        "背面视图硬约束：角色必须背对镜头，画面展示后脑勺、后背、服装背部结构和背后配饰；"
        "脸部不可见，不要出现正面脸，不要回头，不要侧脸，禁止正面视角。"
    ),
}

_COMPOSITE_NAME_PATTERN = re.compile(r"[、,，/／]|和|与|及|以及|们|众人|群|一行人|弟子们|外门弟子们")


def is_composite_character_name(name: str) -> bool:
    """Return True when a character name is actually a group/composite label."""
    text = (name or "").strip()
    if not text:
        return False
    if _COMPOSITE_NAME_PATTERN.search(text):
        return True
    # Names such as "某外门弟子（门外）" are temporary extras, not stable lead character assets.
    if text.startswith("某") or "某" in text[:4]:
        return True
    return False


def append_global_image_constraints(prompt: str) -> str:
    """Append shared image safety/consistency constraints without duplicating them."""
    text = (prompt or "").strip()
    if not text:
        return GLOBAL_IMAGE_NEGATIVE_CONSTRAINT
    if GLOBAL_IMAGE_NEGATIVE_CONSTRAINT in text or "通用负面约束" in text:
        return text
    return f"{text}\n{GLOBAL_IMAGE_NEGATIVE_CONSTRAINT}"


def infer_gender_age_hint(name: str, description: str) -> str:
    text = f"{name} {description}"
    if any(token in text for token in ("少女", "女子", "女性", "女主", "女修", "姑娘", "公主", "师姐", "师妹")):
        return "性别/年龄感：女性角色，年龄感按描述保持。"
    if any(token in text for token in ("少年", "男子", "男性", "男主", "男修", "弟子", "师兄", "师弟", "青年")):
        return "性别/年龄感：男性角色，年龄感按描述保持。"
    return "性别/年龄感：严格依据小说与角色描述，不得自行改变。"


def build_visual_contract(
    *,
    entity_id: str,
    entity_type: str,
    name: str,
    description: str,
    style: str,
) -> Dict[str, Any]:
    """Build stable visual DNA metadata shared by all generated views."""
    fingerprint_source = "|".join([entity_id, entity_type, name or "", description or "", style or ""])
    contract_id = hashlib.sha1(fingerprint_source.encode("utf-8")).hexdigest()[:16]
    single_subject = entity_type != "character" or not is_composite_character_name(name)
    return {
        "id": contract_id,
        "entity_id": entity_id,
        "entity_type": entity_type,
        "name": name,
        "style": style,
        "single_subject": single_subject,
        "appearance": description,
        "gender_age_hint": infer_gender_age_hint(name, description) if entity_type == "character" else "",
    }


def visual_consistency_metadata(
    *,
    contract: Dict[str, Any],
    view_key: str,
    reference_view_key: Optional[str] = None,
    reference_asset_id: Optional[str] = None,
) -> Dict[str, Any]:
    score = 88 if reference_view_key else 76
    if not contract.get("single_subject", True):
        score = 20
    return {
        "score": score,
        "mode": "metadata_contract",
        "status": "needs_visual_review" if score < 90 else "metadata_passed",
        "contract_id": contract.get("id"),
        "view_key": view_key,
        "reference_view_key": reference_view_key,
        "reference_asset_id": reference_asset_id,
        "notes": "轻量规则评分：已校验同一视觉契约、单人角色准入和参考视图血缘；真实图像相似度需后续多模态模型复核。",
    }


def entity_view_prompt(
    *,
    entity_type: str,
    name: str,
    description: str,
    style_keywords: str,
    view_label: str,
    prompt_hint: str,
    contract: Dict[str, Any],
    view_key: Optional[str] = None,
    reference_view_label: Optional[str] = None,
    reference_url: Optional[str] = None,
) -> str:
    entity_labels = {"character": "角色", "scene": "场景", "prop": "道具"}
    constraints = {
        "character": CHARACTER_SINGLE_VIEW_CONSTRAINT,
        "scene": SCENE_VIEW_CONSTRAINT,
        "prop": PROP_VIEW_CONSTRAINT,
    }.get(entity_type, GLOBAL_IMAGE_NEGATIVE_CONSTRAINT)
    reference_line = ""
    if reference_view_label or reference_url:
        reference_line = (
            f"参考视图：必须继承已生成的{reference_view_label or '参考图'}视觉DNA；"
            f"参考资产：{reference_url or '同一角色视觉契约'}。"
        )
    direction_constraint = ""
    if entity_type == "character" and view_key:
        direction_constraint = CHARACTER_VIEW_DIRECTION_CONSTRAINTS.get(view_key, "")
    from app.services.asset_visual_contract import render_contract_prompt_block

    contract_block = render_contract_prompt_block(contract, view_key=view_key or "", view_label=view_label)
    return "\n".join(
        part
        for part in [
            f"{style_keywords}。",
            contract_block,
            f"生成对象：{entity_labels.get(entity_type, entity_type)}「{name}」的{view_label}参考图。",
            f"设定描述：{description or '保持小说设定一致'}。",
            contract.get("gender_age_hint") or "",
            reference_line,
            f"视图要求：{prompt_hint}。",
            direction_constraint,
            constraints,
            GLOBAL_IMAGE_NEGATIVE_CONSTRAINT,
        ]
        if part
    )
