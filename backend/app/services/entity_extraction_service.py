"""
Deterministic story entity extraction.
"""

from __future__ import annotations

import re
from typing import Any

ENTITY_TYPES = {"character", "scene", "prop", "event"}

CHARACTER_RE = re.compile(r"(?:角色|人物|主角|配角)[:：]\s*([^\n，。；;]+)")
SCENE_RE = re.compile(r"(?:场景|地点|场地)[:：]\s*([^\n，。；;]+)")
PROP_RE = re.compile(r"(?:道具|物品|装备)[:：]\s*([^\n，。；;]+)")
EVENT_RE = re.compile(r"(?:事件|剧情|发生)[:：]\s*([^\n，。；;]+)")
EXPLICIT_CHARACTER_RE = re.compile(
    r"(?:角色|人物|主角|配角)[:：]\s*([^\n，。；;]+)|"
    r"([\u4e00-\u9fff]{2,4})(?:说|问|喊|叫道|说道|低声道|名字叫|名为)"
)
PERSON_ACTION_RE = re.compile(
    r"(?<![\u4e00-\u9fff])([\u4e00-\u9fff]{2,4})"
    r"(?:低声道|说道|叫道|说|问|喊|在|从|向|对|把|将|醒来|发现|看见|拿起|抬手|转身)"
)
SCENE_SUFFIXES = (
    "外门石屋",
    "石屋",
    "木屋",
    "房间",
    "洞府",
    "山门",
    "宗门",
    "外门",
    "内门",
    "城门",
    "宫殿",
    "大殿",
    "殿",
    "宫",
    "城",
    "街",
    "巷",
    "谷",
    "山",
    "林",
    "森林",
    "港口",
    "船舱",
    "实验室",
)
PROP_SUFFIXES = (
    "玉佩",
    "戒指",
    "令牌",
    "钥匙",
    "铜钩",
    "钩",
    "剑",
    "刀",
    "枪",
    "符",
    "丹",
    "药",
    "书",
    "灯",
    "铃",
    "镜",
    "甲",
    "衣",
    "披风",
    "芯片",
)
CHARACTER_TITLE_SUFFIXES = (
    "执事",
    "长老",
    "掌门",
    "师父",
    "师尊",
    "师兄",
    "师弟",
    "师姐",
    "师妹",
    "公子",
    "姑娘",
    "少主",
    "圣女",
)
GROUP_CHARACTER_WORDS = (
    "们",
    "众人",
    "人群",
    "一行人",
    "弟子们",
    "外门弟子",
    "内门弟子",
    "守卫们",
    "侍卫们",
    "士兵们",
    "路人",
    "群众",
)
CHARACTER_CONTEXT_CUES = (
    "主角",
    "少女",
    "少年",
    "女子",
    "男子",
    "女性",
    "男性",
    "女主",
    "男主",
    "角色",
    "人物",
    "执事",
    "长老",
    "说话",
    "低声",
    "开口",
    "行动",
    "醒来",
)
SCENE_CONTEXT_CUES = ("场景", "地点", "场地", "空间", "建筑", "室内", "室外", "醒来的地点", "环境")
PROP_CONTEXT_CUES = ("道具", "物品", "装备", "法器", "悬在", "佩戴", "握着", "拿着", "核心道具")
EVENT_CONTEXT_CUES = ("事件", "剧情", "发现", "遭遇", "决定", "战斗", "逃离", "抵达", "爆发")
NON_CHARACTER_WORDS = {
    "疼痛",
    "狂喜",
    "活着",
    "阳光",
    "年轻",
    "瘦弱",
    "身躯",
    "眼睛",
    "双手",
    "起身",
    "个人",
    "没有人",
    "外门",
    "弟子",
    "修炼",
    "灵气",
    "气息",
    "房间",
    "记忆",
    "前世",
    "今生",
    "声音",
    "画面",
    "镜头",
}


def _clean_name(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip(" ：:，。；;、“”\"'\t\n")
    cleaned = re.split(r"[。！？!?]|\b(?:角色|人物|主角|配角|场景|地点|场地|道具|物品|装备|事件|剧情|发生)[:：]", cleaned)[0]
    return cleaned.strip(" ：:，。；;、“”\"'\t\n")


def _split_entity_names(value: str) -> list[str]:
    cleaned = _clean_name(value)
    if not cleaned:
        return []
    if not re.search(r"[、,，/／]", cleaned):
        return [cleaned]
    return [_clean_name(part) for part in re.split(r"[、,，/／]", cleaned) if _clean_name(part)]


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _endswith_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(text.endswith(marker) for marker in markers)


def _is_group_or_non_character_name(name: str) -> bool:
    text = name.strip()
    if not text:
        return True
    if text in NON_CHARACTER_WORDS:
        return True
    return _contains_any(text, GROUP_CHARACTER_WORDS)


def _looks_like_chinese_person_name(name: str) -> bool:
    if _is_group_or_non_character_name(name):
        return False
    return bool(re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name))


def _normalize_name_for_type(entity_type: str, name: str) -> str:
    cleaned = _clean_name(name)
    if entity_type == "prop":
        cleaned = re.sub(r"^.*(?:别碰|触碰|拿起|拿着|握着|取出|举起|发现|佩戴|拔出|听见|把|将)", "", cleaned)
    if entity_type == "scene":
        cleaned = re.sub(r"^(?:在|到|至|抵达|进入|离开|前往|来到|走进)", "", cleaned)
    return _clean_name(cleaned)


def _infer_entity_type(
    declared_type: str,
    name: str,
    description: str | None = None,
    evidence: str | None = None,
) -> str | None:
    context = f"{name} {description or ''} {evidence or ''}"
    if _is_group_or_non_character_name(name) and declared_type == "character":
        return None
    has_character_context = (
        _endswith_any(name, CHARACTER_TITLE_SUFFIXES)
        or (
            _looks_like_chinese_person_name(name)
            and (declared_type == "character" or _contains_any(context, CHARACTER_CONTEXT_CUES))
        )
    )
    has_multi_char_prop_suffix = any(name.endswith(marker) for marker in PROP_SUFFIXES if len(marker) > 1)
    has_prop_suffix = _endswith_any(name, PROP_SUFFIXES)
    if has_character_context and not has_multi_char_prop_suffix:
        return "character"
    if has_multi_char_prop_suffix or (_contains_any(context, PROP_CONTEXT_CUES) and has_prop_suffix):
        return "prop"
    if _endswith_any(name, SCENE_SUFFIXES):
        return "scene"
    if _contains_any(context, SCENE_CONTEXT_CUES) and not _looks_like_chinese_person_name(name):
        return "scene"
    if has_character_context:
        return "character"
    if declared_type == "event" or _contains_any(context, EVENT_CONTEXT_CUES):
        return "event"
    if declared_type in ENTITY_TYPES:
        return declared_type
    return None


def _append_normalized_entity(
    normalized: list[dict[str, Any]],
    entity: dict[str, Any],
    seen: set[tuple[str, str]],
) -> None:
    key = (entity["entity_type"], entity["name"])
    if key in seen:
        return
    for index, existing in enumerate(normalized):
        if existing["entity_type"] != entity["entity_type"]:
            continue
        existing_name = existing["name"]
        if existing_name in entity["name"] and len(entity["name"]) > len(existing_name):
            seen.discard((existing["entity_type"], existing_name))
            normalized[index] = entity
            seen.add(key)
            return
        if entity["name"] in existing_name:
            return
    normalized.append(entity)
    seen.add(key)


def normalize_extracted_entities(
    entities: list[dict[str, Any]],
    requested_types: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Correct obvious role/scene/prop mismatches before assets are created."""
    requested = requested_types or ENTITY_TYPES
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in entities:
        declared_type = str(item.get("entity_type") or item.get("type") or "").strip()
        raw_name = str(item.get("name") or item.get("title") or "").strip()
        if declared_type not in ENTITY_TYPES:
            continue
        for name in _split_entity_names(raw_name):
            inferred_type = _infer_entity_type(
                declared_type,
                name,
                item.get("description"),
                item.get("evidence"),
            )
            if not inferred_type or inferred_type not in requested:
                continue
            cleaned_name = _normalize_name_for_type(inferred_type, name)
            if not cleaned_name:
                continue
            attrs = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
            if inferred_type != declared_type:
                attrs = {
                    **attrs,
                    "classification_corrected_from": declared_type,
                    "classification_reason": "规则校正：名称、描述和原文证据更符合当前实体类型",
                }
            entity = {
                "entity_type": inferred_type,
                "name": cleaned_name[:200],
                "description": item.get("description") or item.get("evidence"),
                "aliases": item.get("aliases") if isinstance(item.get("aliases"), list) else [],
                "attributes": attrs,
                "evidence": item.get("evidence") or item.get("description"),
                "confidence": item.get("confidence") or 90,
                "source": item.get("source") or "deterministic",
            }
            _append_normalized_entity(normalized, entity, seen)
    return normalized


def _add_entity(
    entities: list[dict[str, Any]],
    seen: set[tuple[str, str]],
    entity_type: str,
    name: str,
    description: str,
    evidence: str,
) -> None:
    for cleaned in _split_entity_names(name):
        if not cleaned:
            continue
        key = (entity_type, cleaned)
        if key in seen:
            continue
        seen.add(key)
        entities.append(
            {
                "entity_type": entity_type,
                "name": cleaned[:200],
                "description": description[:500] if description else None,
                "aliases": [],
                "attributes": {},
                "evidence": evidence[:500] if evidence else None,
                "confidence": 100,
                "source": "deterministic",
            }
        )


def extract_story_entities(text: str, requested_types: set[str] | None = None) -> list[dict[str, Any]]:
    """Extract entities with stable local rules for DEV_MODE and tests."""
    requested = requested_types or ENTITY_TYPES
    unknown = requested - ENTITY_TYPES
    if unknown:
        raise ValueError(f"不支持的实体类型: {', '.join(sorted(unknown))}")

    source_text = text or ""
    entities: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    regex_specs = [
        ("character", CHARACTER_RE, "文本标注角色"),
        ("scene", SCENE_RE, "文本标注场景"),
        ("prop", PROP_RE, "文本标注道具"),
        ("event", EVENT_RE, "文本标注事件"),
    ]

    for entity_type, pattern, description in regex_specs:
        if entity_type not in requested:
            continue
        for match in pattern.finditer(source_text):
            _add_entity(entities, seen, entity_type, match.group(1), description, match.group(0))

    if "character" in requested:
        for match in EXPLICIT_CHARACTER_RE.finditer(source_text):
            name = match.group(1) or match.group(2)
            if not name:
                continue
            name = _clean_name(name)
            if name.startswith(("第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十")):
                continue
            if name in NON_CHARACTER_WORDS:
                continue
            window = source_text[max(0, match.start() - 16): match.end() + 24]
            _add_entity(entities, seen, "character", name, "规则识别人物", window)
        for match in PERSON_ACTION_RE.finditer(source_text):
            name = _clean_name(match.group(1))
            if (
                not name
                or name.startswith(("第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十"))
                or _is_group_or_non_character_name(name)
                or (len(name) > 2 and _contains_any(name, PROP_SUFFIXES))
                or _endswith_any(name, SCENE_SUFFIXES)
            ):
                continue
            window = source_text[max(0, match.start() - 16): match.end() + 24]
            _add_entity(entities, seen, "character", name, "规则识别人物动作", window)

    if "scene" in requested:
        for marker in SCENE_SUFFIXES:
            pattern = re.compile(rf"(?:在|到|至|抵达|进入|离开|前往)([\u4e00-\u9fff]{{1,8}}{marker})")
            for match in pattern.finditer(source_text):
                _add_entity(entities, seen, "scene", match.group(1), "规则识别地点", match.group(0))

    if "prop" in requested:
        for marker in PROP_SUFFIXES:
            pattern = re.compile(rf"[\u4e00-\u9fff]{{0,6}}{marker}")
            for match in pattern.finditer(source_text):
                _add_entity(entities, seen, "prop", match.group(0), "规则识别道具", match.group(0))

    if "event" in requested:
        sentences = re.split(r"[。！？!?\n]\s*", source_text)
        for sentence in sentences:
            sentence = _clean_name(re.sub(r"^(?:事件|剧情|发生)[:：]\s*", "", sentence))
            if any(marker in sentence for marker in ("发现", "遭遇", "决定", "战斗", "逃离", "抵达", "失踪", "爆发")):
                _add_entity(entities, seen, "event", sentence[:40], "规则识别事件", sentence)

    return normalize_extracted_entities(entities, requested)


def build_story_bible_sections(entities: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    sections = {
        "character_rules": [],
        "scene_rules": [],
        "prop_rules": [],
        "event_timeline": [],
    }
    for entity in entities:
        item = {
            "name": entity["name"],
            "description": entity.get("description") or entity.get("evidence") or "",
            "source_entity_id": entity.get("id"),
        }
        if entity["entity_type"] == "character":
            sections["character_rules"].append(item)
        elif entity["entity_type"] == "scene":
            sections["scene_rules"].append(item)
        elif entity["entity_type"] == "prop":
            sections["prop_rules"].append(item)
        elif entity["entity_type"] == "event":
            sections["event_timeline"].append({"title": entity["name"], **item})
    return sections
