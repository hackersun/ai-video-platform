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
    cleaned = re.sub(r"\s+", " ", value).strip(" ：:，。；;、\t\n")
    cleaned = re.split(r"[。！？!?]|\b(?:角色|人物|主角|配角|场景|地点|场地|道具|物品|装备|事件|剧情|发生)[:：]", cleaned)[0]
    return cleaned.strip(" ：:，。；;、\t\n")


def _add_entity(
    entities: list[dict[str, Any]],
    seen: set[tuple[str, str]],
    entity_type: str,
    name: str,
    description: str,
    evidence: str,
) -> None:
    cleaned = _clean_name(name)
    if not cleaned:
        return
    key = (entity_type, cleaned)
    if key in seen:
        return
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

    if "scene" in requested:
        for marker in ("城", "山", "谷", "殿", "宫", "街", "巷", "实验室", "港口", "森林"):
            pattern = re.compile(rf"(?:在|到|至|抵达|进入|离开|前往)([\u4e00-\u9fff]{{1,8}}{marker})")
            for match in pattern.finditer(source_text):
                _add_entity(entities, seen, "scene", match.group(1), "规则识别地点", match.group(0))

    if "prop" in requested:
        for marker in ("剑", "刀", "枪", "玉佩", "芯片", "钥匙", "戒指", "书", "令牌"):
            pattern = re.compile(rf"[\u4e00-\u9fff]{{0,6}}{marker}")
            for match in pattern.finditer(source_text):
                _add_entity(entities, seen, "prop", match.group(0), "规则识别道具", match.group(0))

    if "event" in requested:
        sentences = re.split(r"[。！？!?\n]\s*", source_text)
        for sentence in sentences:
            sentence = _clean_name(re.sub(r"^(?:事件|剧情|发生)[:：]\s*", "", sentence))
            if any(marker in sentence for marker in ("发现", "遭遇", "决定", "战斗", "逃离", "抵达", "失踪", "爆发")):
                _add_entity(entities, seen, "event", sentence[:40], "规则识别事件", sentence)

    return entities


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
