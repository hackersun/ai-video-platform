"""Story-linked visual contracts for reusable assets.

The builder is intentionally deterministic: it only compacts existing story
context, entity fields, and structured rule data. It never calls an AI model.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StoryBible
from app.services.story_prompt_context import compact_text, load_story_prompt_context


SUPPORTED_ENTITY_TYPES = {"character", "scene", "prop"}


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in re.split(r"[、,，;；\n]+", text) if part.strip()]


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, list):
            text = "、".join(str(item).strip() for item in value if str(item).strip())
        else:
            text = str(value).strip()
        if text:
            return text
    return ""


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def _stable_hash(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()[:20]


def _entity_value(entity: Any, key: str, default: Any = None) -> Any:
    if isinstance(entity, dict):
        return entity.get(key, default)
    return getattr(entity, key, default)


def _entity_type(entity: Any) -> str:
    return str(_entity_value(entity, "entity_type") or _entity_value(entity, "category") or "").strip()


def _entity_attrs(entity: Any) -> Dict[str, Any]:
    return _as_dict(_entity_value(entity, "attributes")) or _as_dict(_entity_value(entity, "generation_params"))


def _names_match(rule: Dict[str, Any], name: str) -> bool:
    rule_name = str(rule.get("name") or rule.get("title") or "").strip()
    aliases = [str(alias).strip() for alias in _as_list(rule.get("aliases"))]
    candidates = [rule_name, *aliases]
    return any(candidate and (candidate == name or name in candidate or candidate in name) for candidate in candidates)


def _merge_values(current: Any, incoming: Any) -> Any:
    if incoming in (None, "", [], {}):
        return current
    if current in (None, "", [], {}):
        return incoming
    if isinstance(current, dict) and isinstance(incoming, dict):
        return _merge_rule_dicts(current, incoming)
    if isinstance(current, list) and isinstance(incoming, list):
        merged = list(current)
        seen = {str(item) for item in merged}
        for item in incoming:
            marker = str(item)
            if marker not in seen:
                merged.append(item)
                seen.add(marker)
        return merged
    return current


def _merge_rule_dicts(*rules: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for rule in rules:
        for key, value in rule.items():
            merged[key] = _merge_values(merged.get(key), value)
    return merged


def _story_bible_rule_list(story_bible: Optional[StoryBible], entity_type: str) -> List[Dict[str, Any]]:
    if not story_bible:
        return []
    list_key = {
        "character": "character_rules",
        "scene": "scene_rules",
        "prop": "prop_rules",
    }[entity_type]
    return [_as_dict(item) for item in (getattr(story_bible, list_key, None) or []) if isinstance(item, dict)]


async def _load_story_bible(db: AsyncSession, user_id: str, context: Dict[str, Any]) -> Optional[StoryBible]:
    if context.get("story_bible_id"):
        result = await db.execute(
            select(StoryBible).where(
                and_(StoryBible.id == context["story_bible_id"], StoryBible.user_id == user_id)
            )
        )
        return result.scalar_one_or_none()
    if context.get("novel_id"):
        result = await db.execute(
            select(StoryBible)
            .where(and_(StoryBible.user_id == user_id, StoryBible.novel_id == context["novel_id"]))
            .order_by(desc(StoryBible.updated_at))
            .limit(1)
        )
        return result.scalar_one_or_none()
    return None


async def _matching_rule(
    db: AsyncSession,
    user_id: str,
    context: Dict[str, Any],
    entity_type: str,
    name: str,
) -> Dict[str, Any]:
    list_key = {"character": "characters", "scene": "scenes", "prop": "props"}[entity_type]
    candidates: List[Dict[str, Any]] = []
    for item in context.get(list_key) or []:
        rule = _as_dict(item)
        if rule and _names_match(rule, name):
            candidates.append(rule)

    story_bible = await _load_story_bible(db, user_id, context)
    for rule in _story_bible_rule_list(story_bible, entity_type):
        if rule and _names_match(rule, name):
            candidates.append(rule)

    return _merge_rule_dicts(*candidates) if candidates else {}


def _collect_source_text(context: Dict[str, Any], entity: Any, rule: Dict[str, Any], style: str) -> str:
    attrs = _entity_attrs(entity)
    parts = [
        context.get("title"),
        context.get("genre"),
        context.get("description"),
        context.get("style"),
        context.get("worldview"),
        context.get("chapter_title"),
        context.get("chapter_summary"),
        context.get("script_title"),
        context.get("script_summary"),
        context.get("negative_prompt"),
        _entity_value(entity, "description"),
        _entity_value(entity, "appearance"),
        _entity_value(entity, "visual_prompt"),
        _stable_json(attrs) if attrs else "",
        _stable_json(rule) if rule else "",
        style,
    ]
    return "\n".join(str(part).strip() for part in parts if str(part or "").strip())


def _field(*containers: Dict[str, Any], keys: Iterable[str]) -> Any:
    for container in containers:
        for key in keys:
            value = container.get(key)
            if value not in (None, "", [], {}):
                return value
    return None


def _nested(*containers: Dict[str, Any], names: Iterable[str]) -> Dict[str, Any]:
    for container in containers:
        for name in names:
            value = container.get(name)
            if isinstance(value, dict):
                return value
    return {}


def _source_text(context: Dict[str, Any], entity: Any, attrs: Dict[str, Any]) -> str:
    parts = [
        context.get("description"),
        context.get("worldview"),
        context.get("chapter_summary"),
        context.get("script_summary"),
        context.get("negative_prompt"),
        _entity_value(entity, "description"),
        _entity_value(entity, "appearance"),
        _entity_value(entity, "visual_prompt"),
        _stable_json(attrs) if attrs else "",
    ]
    return "\n".join(str(part).strip() for part in parts if str(part or "").strip())


def _first_match(text: str, patterns: Iterable[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip(" ，,。；;、")
    return ""


def _known_phrase(text: str, phrases: Iterable[str]) -> str:
    for phrase in phrases:
        if phrase in text:
            return phrase
    return ""


def _source_items(text: str, patterns: Iterable[str]) -> List[str]:
    items: List[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            item = match.group(1).strip(" ，,。；;、")
            if item and item not in items:
                items.append(item)
    return items


def _scene_fallbacks(source_text: str) -> Dict[str, Any]:
    fixed_elements = _source_items(
        source_text,
        (
            r"((?:左侧|右侧|后墙|前墙|中央|中间|门口|柜台前)[^，,。；;、\n]{1,24})",
        ),
    )
    return {
        "era": _first_match(source_text, (r"(\d{4}年代(?:小城|城市|县城|乡镇|港口|街区)?)",)),
        "weather": _known_phrase(source_text, ("雨夜", "雪夜", "暴雨", "小雨", "阴天", "晴天", "冷雾", "薄雾")),
        "lighting_direction": _first_match(
            source_text,
            (
                r"((?:门外|室外|窗外)[^。；;\n]{0,40}?(?:灯|光)[，,][^。；;\n]{0,40}?(?:灯|光))",
                r"((?:光源方向|光源|灯光)[:：][^。；;\n]+)",
            ),
        ),
        "fixed_elements": fixed_elements,
    }


def _character_fallbacks(source_text: str) -> Dict[str, Any]:
    return {
        "age": _first_match(source_text, (r"(\d{1,2}岁(?:少年|少女|青年|女孩|男孩)?)",)),
        "appearance": _known_phrase(source_text, ("银灰短发", "黑色短发", "长发", "瘦削脸型")),
        "wardrobe": _first_match(
            source_text,
            (r"((?:蓝色|灰蓝|黑色|白色|红色|旧式)[^，,。；;、\n]{0,12}(?:夹克|长衫|校服|外套|工装))",),
        ),
        "signature_items": _source_items(source_text, (r"([^，,。；;、\n]{0,8}手套)", r"([^，,。；;、\n]{0,8}罗盘)")),
    }


def _prop_fallbacks(source_text: str) -> Dict[str, Any]:
    return {
        "material": _first_match(source_text, (r"((?:青铜|旧铜|木质|铁质|银质|陶瓷)[^，,。；;、\n]{0,4})",)),
        "scale": _known_phrase(source_text, ("巴掌大小", "半人高", "指节大小")),
        "fixed_marks": _source_items(
            source_text,
            (r"(裂纹中泛青光)", r"(红绳)", r"([^，,。；;、\n]{0,8}裂纹)"),
        ),
    }


def _scene_contract(
    rule: Dict[str, Any],
    attrs: Dict[str, Any],
    context: Dict[str, Any],
    entity: Any,
) -> Dict[str, Any]:
    dna = _nested(rule, attrs, names=("scene_dna", "continuity_axes", "visual_dna"))
    layout = _nested(rule, attrs, dna, names=("spatial_layout", "layout"))
    fallbacks = _scene_fallbacks(_source_text(context, entity, attrs))
    continuity_axes = {
        "era": _first_text(_field(rule, attrs, dna, keys=("era", "period", "time_period", "age")), fallbacks["era"]),
        "weather": _first_text(_field(rule, attrs, dna, keys=("weather", "climate")), fallbacks["weather"]),
        "lighting_direction": _first_text(
            _field(rule, attrs, dna, keys=("lighting_direction", "lighting", "light", "light_source")),
            fallbacks["lighting_direction"],
        ),
        "color_palette": _first_text(_field(rule, attrs, dna, keys=("color_palette", "palette", "colors"))),
    }
    spatial_layout = {
        "fixed_elements": _as_list(_field(rule, attrs, dna, layout, keys=("fixed_elements", "fixed", "anchors")))
        or fallbacks["fixed_elements"],
        "action_zones": _as_list(_field(rule, attrs, dna, layout, keys=("action_zones", "zones"))),
        "forbidden_changes": _as_list(
            _field(rule, attrs, dna, layout, keys=("forbidden_changes", "negative_constraints", "do_not_change"))
        ),
    }
    return {
        "continuity_axes": continuity_axes,
        "spatial_layout": spatial_layout,
        "negative_constraints": _as_list(context.get("negative_prompt")) + spatial_layout["forbidden_changes"],
    }


def _character_contract(
    rule: Dict[str, Any],
    attrs: Dict[str, Any],
    entity: Any,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    dna = _nested(rule, attrs, names=("identity", "visual_dna", "character_dna"))
    fallbacks = _character_fallbacks(_source_text(context, entity, attrs))
    identity = {
        "age": _first_text(_field(rule, attrs, dna, keys=("age", "age_look", "age_range")), fallbacks["age"]),
        "appearance": _first_text(
            _field(rule, attrs, dna, keys=("appearance", "face", "hair", "body")),
            _entity_value(entity, "appearance"),
            fallbacks["appearance"],
            _entity_value(entity, "description"),
        ),
        "wardrobe": _first_text(
            _field(rule, attrs, dna, keys=("wardrobe", "costume", "clothing", "outfit")),
            fallbacks["wardrobe"],
        ),
        "signature_items": _as_list(_field(rule, attrs, dna, keys=("signature_items", "items", "props")))
        or fallbacks["signature_items"],
    }
    return {"identity": identity}


def _prop_contract(rule: Dict[str, Any], attrs: Dict[str, Any], context: Dict[str, Any], entity: Any) -> Dict[str, Any]:
    dna = _nested(rule, attrs, names=("prop_dna", "visual_dna"))
    fallbacks = _prop_fallbacks(_source_text(context, entity, attrs))
    return {
        "prop_dna": {
            "material": _first_text(_field(rule, attrs, dna, keys=("material", "texture")), fallbacks["material"]),
            "scale": _first_text(_field(rule, attrs, dna, keys=("scale", "size")), fallbacks["scale"]),
            "fixed_marks": _as_list(_field(rule, attrs, dna, keys=("fixed_marks", "marks", "signature_marks")))
            or fallbacks["fixed_marks"],
        }
    }


async def build_visual_contract_from_story(
    db: AsyncSession,
    user_id: str,
    *,
    entity: Any,
    style: str,
    chapter_id: Optional[str] = None,
    script_id: Optional[str] = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Build a compact visual contract for a character, scene, or prop."""
    entity_id = str(_entity_value(entity, "id") or "").strip()
    entity_type = _entity_type(entity)
    entity_name = str(_entity_value(entity, "name") or "").strip()
    if entity_type not in SUPPORTED_ENTITY_TYPES:
        raise ValueError(f"Unsupported asset visual contract entity type: {entity_type}")
    if not entity_id or not entity_name:
        raise ValueError("Visual contract entity must include id and name")

    resolved_chapter_id = chapter_id or _entity_value(entity, "chapter_id")
    resolved_script_id = script_id or _entity_value(entity, "script_id")
    context = await load_story_prompt_context(
        db,
        user_id,
        novel_id=_entity_value(entity, "novel_id"),
        chapter_id=resolved_chapter_id,
        script_id=resolved_script_id,
        style=style,
    )
    rule = await _matching_rule(db, user_id, context, entity_type, entity_name)
    attrs = _entity_attrs(entity)
    source_text = _collect_source_text(context, entity, rule, style)
    contract_hash = _stable_hash(
        {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "entity_name": entity_name,
            "style": style,
            "source_text": source_text,
        }
    )

    contract: Dict[str, Any] = {
        "contract_id": f"visual-contract-{contract_hash}",
        "force_refresh": bool(force_refresh),
        "entity_id": entity_id,
        "entity_type": entity_type,
        "entity_name": entity_name,
        "style": style,
        "story_scope": {
            "novel_id": context.get("novel_id"),
            "chapter_id": context.get("chapter_id"),
            "script_id": context.get("script_id"),
        },
        "novel_id": context.get("novel_id"),
        "chapter_id": context.get("chapter_id"),
        "script_id": context.get("script_id"),
        "context_sources": {
            "title": context.get("title"),
            "story_bible_id": context.get("story_bible_id"),
            "style": context.get("style") or style,
            "worldview": context.get("worldview"),
            "chapter_title": context.get("chapter_title"),
            "script_title": context.get("script_title"),
            "negative_prompt": context.get("negative_prompt"),
        },
        "matched_rule": rule,
        "source_text": compact_text(source_text, 1600),
    }

    if entity_type == "scene":
        contract.update(_scene_contract(rule, attrs, context, entity))
    elif entity_type == "character":
        contract.update(_character_contract(rule, attrs, entity, context))
        contract["negative_constraints"] = _as_list(context.get("negative_prompt"))
    elif entity_type == "prop":
        contract.update(_prop_contract(rule, attrs, context, entity))
        contract["negative_constraints"] = _as_list(context.get("negative_prompt"))

    return contract


def _render_list(label: str, values: Iterable[str]) -> List[str]:
    items = [str(value).strip() for value in values if str(value).strip()]
    return [f"{label}：{'、'.join(items)}"] if items else []


def render_contract_prompt_block(contract: Dict[str, Any], *, view_key: str, view_label: str) -> str:
    """Render a Chinese prompt block for one generated asset view."""
    context_sources = _as_dict(contract.get("context_sources"))
    scope = _as_dict(contract.get("story_scope"))
    lines = [
        "【小说关联视觉契约】",
        f"资产：{contract.get('entity_name')}（{contract.get('entity_type')}）",
        f"视图：{view_label}（{view_key}）",
        f"故事范围：小说 {scope.get('novel_id') or '-'} / 章节 {scope.get('chapter_id') or '-'} / 剧本 {scope.get('script_id') or '-'}",
    ]
    if context_sources.get("title"):
        lines.append(f"作品：{context_sources.get('title')}")
    if context_sources.get("worldview"):
        lines.append(f"世界观：{compact_text(context_sources.get('worldview'), 180)}")
    if context_sources.get("style"):
        lines.append(f"风格：{compact_text(context_sources.get('style'), 120)}")
    if context_sources.get("chapter_title") or context_sources.get("script_title"):
        lines.append(
            f"来源：章节《{context_sources.get('chapter_title') or '-'}》 / 剧本《{context_sources.get('script_title') or '-'}》"
        )

    entity_type = contract.get("entity_type")
    if entity_type == "scene":
        axes = _as_dict(contract.get("continuity_axes"))
        layout = _as_dict(contract.get("spatial_layout"))
        lines.extend(
            [
                "连续性轴：",
                f"时代：{axes.get('era') or '-'}",
                f"天气：{axes.get('weather') or '-'}",
                f"光源方向：{axes.get('lighting_direction') or '-'}",
                f"色彩基调：{axes.get('color_palette') or '-'}",
                "空间布局：",
            ]
        )
        lines.extend(_render_list("固定元素", layout.get("fixed_elements") or []))
        lines.extend(_render_list("动作区域", layout.get("action_zones") or []))
        lines.extend(_render_list("禁止变化", layout.get("forbidden_changes") or []))
    elif entity_type == "character":
        identity = _as_dict(contract.get("identity"))
        lines.extend(
            [
                "角色身份：",
                f"年龄：{identity.get('age') or '-'}",
                f"外观：{identity.get('appearance') or '-'}",
                f"服装：{identity.get('wardrobe') or '-'}",
            ]
        )
        lines.extend(_render_list("标志物", identity.get("signature_items") or []))
    elif entity_type == "prop":
        prop_dna = _as_dict(contract.get("prop_dna"))
        lines.extend(
            [
                "道具DNA：",
                f"材质：{prop_dna.get('material') or '-'}",
                f"尺度：{prop_dna.get('scale') or '-'}",
            ]
        )
        lines.extend(_render_list("固定标记", prop_dna.get("fixed_marks") or []))

    negative_constraints = _as_list(context_sources.get("negative_prompt")) + _as_list(
        contract.get("negative_constraints")
    )
    deduped_negatives = list(dict.fromkeys(negative_constraints))
    lines.extend(_render_list("负面约束", deduped_negatives))
    lines.append("硬规则")
    return "\n".join(lines)
