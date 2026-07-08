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
    r"([\u4e00-\u9fff]{2,4})[：:][“\"']|"
    r"(?<![\u4e00-\u9fff])([\u4e00-\u9fff]{2,4}?)(?:坚定地|微笑|小声|低声)?(?:回答|说|问|喊|叫道|说道|低声道|名字叫|名为)"
)
DESCRIPTOR_CHARACTER_RE = re.compile(
    r"(?:星灯猫|女孩|少年|少女|男子|女子)([\u4e00-\u9fff]{2,4}?)(?=(?:蹲|站|走|说|问|低声|小声|，|。|、|在|从|和|一起|$))"
)
PERSON_ACTION_RE = re.compile(
    r"(?<![\u4e00-\u9fff])([\u4e00-\u9fff]{2,4}?)"
    r"(?:低声道|说道|叫道|守在|站在|打在|停在|指向|说|问|喊|在|从|向|把|将|醒来|发现|看见|拿起|抬手|转身)"
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
    "旧码头",
    "码头",
    "修表铺",
    "星锚室",
    "机房",
    "钟楼",
    "灯塔",
    "云灯集市",
    "集市",
    "雨巷",
    "旧伞铺",
    "伞铺",
    "星桥",
    "黎明邮局",
    "邮局",
    "港",
    "铺",
    "船舱",
    "车站",
    "站台",
    "列车",
    "车厢",
    "实验室",
)
PROP_SUFFIXES = (
    "星锚罗盘",
    "罗盘",
    "蓝焰灯芯",
    "灯芯",
    "银色工具包",
    "工具包",
    "铜钥匙",
    "铜铃星灯",
    "铜铃",
    "星形纽扣",
    "纽扣",
    "信封",
    "海潮钟",
    "红围巾",
    "围巾",
    "白色药箱",
    "药箱",
    "病历",
    "信号灯",
    "广告屏",
    "路灯",
    "星锚",
    "图纸",
    "轨道",
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
NON_SCENE_COPY_MARKERS = ("这一刻", "指向", "推向", "注意力", "重新", "保证", "字幕", "对白", "之间")
SCENE_EXACT_TERMS = ("云灯集市", "雨巷", "旧伞铺", "星桥", "黎明邮局", "山城", "钟楼")
PROP_EXACT_TERMS = ("铜铃星灯", "星形纽扣", "信封")
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
    "因果",
    "小说",
    "对白",
    "字幕",
    "字幕要点",
    "保留关键",
    "白并标注",
    "她",
    "他",
    "它",
    "他们",
    "她们",
    "两人",
    "三人",
    "潮水",
    "指针",
    "现在",
    "暴雨",
    "钟声",
    "钟声停",
    "这里的我",
    "档案",
    "墙面",
    "海风",
    "结尾",
    "不是",
    "不是指",
    "而是",
    "星锚不",
    "罗盘指",
    "芯只在他",
    "紧红围巾",
    "她低声说",
    "她低声",
    "许澜说",
    "江屿回答",
    "星光",
    "只是",
    "它不",
    "霓虹",
}
NON_CHARACTER_NAME_MARKERS = (
    "因果",
    "小说",
    "对白",
    "字幕",
    "标注",
    "关键",
    "与",
    "并",
    "低声说",
    "低声",
    "回答",
    "不是",
    "而是",
    "只在",
    "递过去",
    "一扇",
    "留下",
    "来的不",
)
CHARACTER_RECIPIENT_PREFIXES = ("对", "向", "给", "把", "将", "被", "在", "从")
COMMON_CN_SURNAMES = set("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦许何吕施张孔曹严华金魏陶姜谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤")
SINGLE_CHAR_PROP_SUFFIXES = ("剑", "刀", "枪", "符", "丹", "药", "书", "灯", "铃", "镜", "甲", "衣", "钩")
NON_PROP_WORDS = {
    "开场钩",
    "视觉钩",
    "本场视觉钩",
    "成为本场视觉钩",
    "下一集钩",
    "形成下一集钩",
    "最后一句钩",
    "保留最后一句钩",
    "拉镜",
    "推镜",
    "摇镜",
    "运镜",
    "镜",
}
NON_PROP_HOOK_MARKERS = ("开场", "结尾", "视觉", "本场", "下一集", "最后一句", "保留", "形成", "成为")
NON_PROP_CAMERA_MARKERS = ("拉", "推", "摇", "运", "跟", "固定", "全景", "近景", "中景", "远景", "特写")
NON_PROP_COPY_MARKERS = (
    "推向",
    "指向",
    "注意到",
    "注意力",
    "重新",
    "登上",
    "沿",
    "升起",
    "通往",
    "装进",
    "插进",
    "嵌进",
    "选择让",
    "找第一段",
    "通向",
    "反射",
    "记住",
)
EVENT_LIKE_MARKERS = (
    "醒来",
    "发现",
    "遭遇",
    "决定",
    "战斗",
    "逃离",
    "抵达",
    "失踪",
    "爆发",
    "追查",
    "寻找",
    "打开",
    "进入",
    "响",
    "求救",
    "关门",
    "闪过",
    "传来",
)


def _clean_name(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip(" ：:，。；;、“”\"'\t\n")
    cleaned = re.split(r"[。！？!?]|\b(?:角色|人物|主角|配角|场景|地点|场地|道具|物品|装备|事件|剧情|发生)[:：]", cleaned)[0]
    cleaned = re.sub(r"^([\u4e00-\u9fff]{2,6})[（(][^）)]{1,30}[）)]$", r"\1", cleaned)
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
    if len(text) > 2 and text.startswith(CHARACTER_RECIPIENT_PREFIXES):
        return True
    if text in NON_CHARACTER_WORDS:
        return True
    if _contains_any(text, NON_CHARACTER_NAME_MARKERS):
        return True
    if len(text) > 8:
        return True
    return _contains_any(text, GROUP_CHARACTER_WORDS)


def _is_event_like_name(name: str) -> bool:
    text = name.strip()
    return len(text) >= 4 and _contains_any(text, EVENT_LIKE_MARKERS)


def _is_production_copy_prop_name(name: str) -> bool:
    text = name.strip()
    if not text:
        return True
    if _looks_like_person_name_misread_as_prop(text):
        return True
    if text in NON_PROP_WORDS:
        return True
    if text.endswith("钩") and _contains_any(text, NON_PROP_HOOK_MARKERS):
        return True
    if text.endswith("镜") and _contains_any(text, NON_PROP_CAMERA_MARKERS):
        return True
    if _contains_any(text, NON_PROP_COPY_MARKERS) and len(text) > 4:
        return True
    return False


def _looks_like_person_name_misread_as_prop(name: str) -> bool:
    text = name.strip()
    text = re.sub(r"^(?:对|向|给|把|将|被)", "", text)
    if not re.fullmatch(r"[\u4e00-\u9fff]{2,3}", text):
        return False
    return text[0] in COMMON_CN_SURNAMES and _endswith_any(text, SINGLE_CHAR_PROP_SUFFIXES)


def _is_production_copy_scene_name(name: str) -> bool:
    text = name.strip()
    if not text:
        return True
    return _contains_any(text, NON_SCENE_COPY_MARKERS)


def _looks_like_chinese_person_name(name: str) -> bool:
    if _is_group_or_non_character_name(name):
        return False
    return bool(re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name))


def _normalize_name_for_type(entity_type: str, name: str) -> str:
    cleaned = _clean_name(name)
    if entity_type == "character":
        cleaned = re.sub(r"^(?:巡港员|港员|修表师|少年|少女|男子|女子)", "", cleaned)
        cleaned = re.sub(r"(?:坚定地|微笑|小声|低声说|低声道|说道|叫道|回答|低声|说|问|喊|蹲在|站在|站|扶|看|走|冲|握紧|握|拿|抬|转|戴着|戴|指|蜷)$", "", cleaned)
    if entity_type == "prop":
        if "通往" in cleaned:
            target = cleaned.rsplit("通往", 1)[-1]
            return target if len(target) > 1 else ""
        cleaned = re.sub(r"^.*(?:别碰|触碰|拿起|拿着|握着|握紧|握住|取出|举起|发现|认出|佩戴|佩着|戴着|背负|背着|手持|携带|悬挂|挂着|拔出|听见|照出|夺走|举着|摇响|圈住|装进|插进|嵌进|选择让|找第一段|守住|吹灭|合上|刻着|把|将)", "", cleaned)
        cleaned = re.sub(r"^.*(?:推向|指向|注意到|注意力推向)", "", cleaned)
        cleaned = re.sub(r"^(?:着|了|紧|远处|整排)?(?:同一枚|一枚|这枚|那枚|他们用|他用|她用|你|如果|不要让|通往|登上|沿|同样的)?", "", cleaned)
        cleaned = re.sub(r"^整排(?=路灯)", "", cleaned)
        if cleaned.endswith("铜铃") and cleaned not in {"旧铜铃", "铜铃"}:
            cleaned = "铜铃"
        cleaned = re.sub(r"^了第[一二三四五六七八九十0-9]+枚", "", cleaned)
        if cleaned.startswith("未知") and cleaned != "未知":
            return _clean_name(cleaned)
        if "灯塔" in cleaned and cleaned.endswith("星锚"):
            cleaned = "星锚"
        if "从" in cleaned and _endswith_any(cleaned, PROP_SUFFIXES):
            cleaned = cleaned.rsplit("从", 1)[-1]
        if "的" in cleaned and _endswith_any(cleaned, PROP_SUFFIXES):
            cleaned = cleaned.rsplit("的", 1)[-1]
        if re.search(r"[与和]", cleaned) and _endswith_any(cleaned, PROP_SUFFIXES):
            cleaned = re.split(r"[与和]", cleaned)[-1]
    if entity_type == "scene":
        cleaned = re.sub(r"^(?:在|到|至|抵达|进入|离开|前往|来到|走进)", "", cleaned)
        cleaned = re.sub(r"^.*(?:交代|展示|呈现)", "", cleaned)
        for marker in ("站在", "守在", "看向", "走向", "冲向"):
            if marker in cleaned and _endswith_any(cleaned, SCENE_SUFFIXES):
                cleaned = cleaned.rsplit(marker, 1)[-1]
        cleaned = re.sub(r"^(?:空荡)(?=车厢)", "", cleaned)
        for marker in ("穿过", "通往"):
            if marker in cleaned and _endswith_any(cleaned, SCENE_SUFFIXES):
                cleaned = cleaned.rsplit(marker, 1)[-1]
        if "把" in cleaned and _endswith_any(cleaned, SCENE_SUFFIXES):
            cleaned = cleaned.rsplit("把", 1)[-1]
        if "的" in cleaned and _endswith_any(cleaned, SCENE_SUFFIXES):
            cleaned = cleaned.rsplit("的", 1)[-1]
        if "悬在" in cleaned and _endswith_any(cleaned, SCENE_SUFFIXES):
            cleaned = cleaned.rsplit("悬在", 1)[-1]
    return _clean_name(cleaned)


def _infer_weather(context: str) -> str:
    if any(marker in context for marker in ("雨夜", "雨后", "雨水", "下雨", "暴雨", "细雨")):
        return "雨夜" if "夜" in context else "雨后潮湿"
    if any(marker in context for marker in ("雾", "浓雾", "薄雾")):
        return "雾气弥漫"
    if any(marker in context for marker in ("雪", "风雪")):
        return "风雪"
    if "海潮" in context or "码头" in context or "港" in context:
        return "潮湿海风"
    return "常规天气"


def _infer_lighting(context: str) -> str:
    if any(marker in context for marker in ("雨夜", "夜", "月光", "冷蓝")):
        return "冷蓝夜光"
    if any(marker in context for marker in ("晨", "清晨", "黎明")):
        return "清晨柔光"
    if any(marker in context for marker in ("黄昏", "夕阳", "傍晚")):
        return "黄昏暖光"
    if any(marker in context for marker in ("灯", "灯塔", "灯芯", "霓虹")):
        return "人工灯光"
    return "自然光"


def _infer_scene_tags(name: str, context: str) -> list[str]:
    tags: list[str] = []
    indoor_markers = ("屋", "房间", "船舱", "实验室", "机房", "大殿", "殿", "铺", "室")
    outdoor_markers = ("码头", "港", "山", "林", "街", "巷", "桥", "塔", "城门", "谷")
    if _endswith_any(name, indoor_markers):
        tags.append("室内")
    if _endswith_any(name, outdoor_markers) or any(marker in context for marker in outdoor_markers):
        tags.append("室外")
    if any(marker in context for marker in ("夜", "月光", "雨夜")):
        tags.append("夜晚")
    if any(marker in context for marker in ("晨", "清晨", "黎明")):
        tags.append("清晨")
    if any(marker in context for marker in ("追查", "失控", "黑影", "危机", "战斗", "爆发")):
        tags.append("悬疑")
    if not tags:
        tags.append("日常")
    return list(dict.fromkeys(tags))


def _infer_prop_material(name: str, context: str) -> str:
    material_markers = {
        "青铜": "青铜",
        "铜": "铜",
        "银": "银色金属",
        "玉": "玉石",
        "木": "木质",
        "铁": "黑铁",
        "钢": "钢铁",
        "纸": "纸张",
    }
    combined = f"{name} {context}"
    for marker, material in material_markers.items():
        if marker in combined:
            return material
    return "依据原文设定的固定材质"


def _ensure_production_attributes(
    entity_type: str,
    name: str,
    attrs: dict[str, Any],
    *,
    description: str | None = None,
    evidence: str | None = None,
) -> dict[str, Any]:
    """Add production-control metadata without pretending that image assets exist."""
    normalized_attrs = dict(attrs or {})
    context = " ".join(value for value in (name, description, evidence) if value)

    if entity_type == "character":
        visual_dna = dict(normalized_attrs.get("visual_dna") or {})
        visual_dna.setdefault("identity_anchor", name)
        visual_dna.setdefault("silhouette", f"{name} 的稳定头身比例和脸型")
        visual_dna.setdefault("costume", "依据原文固定服装与标志配饰")
        visual_dna.setdefault("palette", "依据作品统一色彩")
        normalized_attrs["visual_dna"] = visual_dna
        requirements = dict(normalized_attrs.get("reference_requirements") or {})
        requirements.setdefault("character_multiview", ["front", "side", "back"])
        normalized_attrs["reference_requirements"] = requirements

    elif entity_type == "scene":
        tags = normalized_attrs.get("scene_tags") or normalized_attrs.get("tags") or []
        if isinstance(tags, str):
            tags = [item.strip() for item in re.split(r"[、,，/／]", tags) if item.strip()]
        if not isinstance(tags, list) or not tags:
            tags = _infer_scene_tags(name, context)
        scene_dna = dict(normalized_attrs.get("scene_dna") or normalized_attrs.get("visual_dna") or {})
        scene_dna.setdefault("identity_anchor", name)
        scene_dna.setdefault("weather", normalized_attrs.get("weather") or _infer_weather(context))
        scene_dna.setdefault("lighting", normalized_attrs.get("lighting") or _infer_lighting(context))
        scene_dna.setdefault("layout", f"{name} 的固定空间结构、入口和行动区")
        normalized_attrs["scene_tags"] = tags
        normalized_attrs["scene_dna"] = scene_dna
        normalized_attrs.setdefault("weather", scene_dna["weather"])
        normalized_attrs.setdefault("lighting", scene_dna["lighting"])
        requirements = dict(normalized_attrs.get("reference_requirements") or {})
        requirements.setdefault("scene_multiview", ["establishing", "layout", "lighting"])
        normalized_attrs["reference_requirements"] = requirements

    elif entity_type == "prop":
        prop_dna = dict(normalized_attrs.get("prop_dna") or normalized_attrs.get("visual_dna") or {})
        prop_dna.setdefault("identity_anchor", name)
        prop_dna.setdefault("material", _infer_prop_material(name, context))
        prop_dna.setdefault("shape", f"{name} 的固定外形和比例")
        prop_dna.setdefault("state_anchor", "状态变化必须由事件驱动并在后续镜头继承")
        normalized_attrs["prop_dna"] = prop_dna
        requirements = dict(normalized_attrs.get("reference_requirements") or {})
        requirements.setdefault("prop_multiview", ["main", "detail", "scale"])
        normalized_attrs["reference_requirements"] = requirements

    return normalized_attrs


def _infer_entity_type(
    declared_type: str,
    name: str,
    description: str | None = None,
    evidence: str | None = None,
) -> str | None:
    context = f"{name} {description or ''} {evidence or ''}"
    if declared_type == "prop" and _is_production_copy_prop_name(name):
        return None
    if declared_type == "scene" and _is_production_copy_scene_name(name):
        return None
    if _is_group_or_non_character_name(name) and declared_type == "character":
        return None
    if declared_type == "character" and _is_event_like_name(name):
        return "event"
    has_character_context = (
        _endswith_any(name, CHARACTER_TITLE_SUFFIXES)
        or (
            _looks_like_chinese_person_name(name)
            and (declared_type == "character" or _contains_any(context, CHARACTER_CONTEXT_CUES))
        )
    )
    has_multi_char_prop_suffix = any(name.endswith(marker) for marker in PROP_SUFFIXES if len(marker) > 1)
    has_prop_suffix = _endswith_any(name, PROP_SUFFIXES)
    if _endswith_any(name, SCENE_SUFFIXES):
        return "scene"
    if has_character_context and not has_multi_char_prop_suffix:
        return "character"
    if has_multi_char_prop_suffix or (_contains_any(context, PROP_CONTEXT_CUES) and has_prop_suffix):
        return "prop"
    if _contains_any(context, SCENE_CONTEXT_CUES) and not _looks_like_chinese_person_name(name):
        return "scene"
    if has_character_context:
        return "character"
    if declared_type == "event" or _contains_any(context, EVENT_CONTEXT_CUES):
        return "event"
    if declared_type == "character":
        return None
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
        if entity["entity_type"] == "character":
            if existing_name in entity["name"]:
                return
            if entity["name"] in existing_name:
                seen.discard((existing["entity_type"], existing_name))
                normalized[index] = entity
                seen.add(key)
                return
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
            name_for_inference = _normalize_name_for_type(declared_type, name)
            if not name_for_inference:
                continue
            inferred_type = _infer_entity_type(
                declared_type,
                name_for_inference,
                item.get("description"),
                item.get("evidence"),
            )
            if not inferred_type or inferred_type not in requested:
                continue
            cleaned_name = _normalize_name_for_type(inferred_type, name_for_inference)
            if not cleaned_name:
                continue
            if inferred_type == "character" and not (
                _looks_like_chinese_person_name(cleaned_name) or _endswith_any(cleaned_name, CHARACTER_TITLE_SUFFIXES)
            ):
                continue
            if inferred_type == "prop" and _is_production_copy_prop_name(cleaned_name):
                continue
            attrs = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
            if inferred_type != declared_type:
                attrs = {
                    **attrs,
                    "classification_corrected_from": declared_type,
                    "classification_reason": "规则校正：名称、描述和原文证据更符合当前实体类型",
                }
            description = item.get("description") or item.get("evidence")
            evidence = item.get("evidence") or item.get("description")
            attrs = _ensure_production_attributes(
                inferred_type,
                cleaned_name,
                attrs,
                description=description,
                evidence=evidence,
            )
            entity = {
                "entity_type": inferred_type,
                "name": cleaned_name[:200],
                "description": description,
                "aliases": item.get("aliases") if isinstance(item.get("aliases"), list) else [],
                "attributes": attrs,
                "evidence": evidence,
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
        for match in DESCRIPTOR_CHARACTER_RE.finditer(source_text):
            name = _clean_name(match.group(1))
            if not name or _is_group_or_non_character_name(name):
                continue
            window = source_text[max(0, match.start() - 16): match.end() + 24]
            _add_entity(entities, seen, "character", name, "规则识别人物描述", window)
        for match in EXPLICIT_CHARACTER_RE.finditer(source_text):
            name = next((group for group in match.groups() if group), None)
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
        for match in re.finditer(r"([\u4e00-\u9fff]{2,4})(?:是|戴着|仍穿|回答|说)", source_text):
            name = _clean_name(match.group(1))
            if (
                not name
                or name.startswith(("第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十"))
                or _is_group_or_non_character_name(name)
                or _endswith_any(name, SCENE_SUFFIXES)
                or _endswith_any(name, PROP_SUFFIXES)
            ):
                continue
            window = source_text[max(0, match.start() - 16): match.end() + 24]
            _add_entity(entities, seen, "character", name, "规则识别人物描述", window)

    if "scene" in requested:
        for term in SCENE_EXACT_TERMS:
            if term in source_text:
                _add_entity(entities, seen, "scene", term, "规则识别地点", term)
        for marker in SCENE_SUFFIXES:
            pattern = re.compile(rf"(?:在|到|至|抵达|进入|离开|前往|来到|走进|去|穿过|登上)([\u4e00-\u9fff]{{0,8}}{marker})")
            for match in pattern.finditer(source_text):
                _add_entity(entities, seen, "scene", match.group(1), "规则识别地点", match.group(0))
            locative_pattern = re.compile(rf"([\u4e00-\u9fff]{{0,8}}{marker})(?:里|中|外|上|下|前|后|边|尽头|中央|在|的|像|从|滑出)")
            for match in locative_pattern.finditer(source_text):
                _add_entity(entities, seen, "scene", match.group(1), "规则识别地点", match.group(0))

    if "prop" in requested:
        for term in PROP_EXACT_TERMS:
            if term in source_text:
                _add_entity(entities, seen, "prop", term, "规则识别道具", term)
        for marker in PROP_SUFFIXES:
            pattern = re.compile(rf"[\u4e00-\u9fff]{{0,6}}{marker}")
            for match in pattern.finditer(source_text):
                _add_entity(entities, seen, "prop", match.group(0), "规则识别道具", match.group(0))

    if "event" in requested:
        sentences = re.split(r"[。！？!?\n]\s*", source_text)
        for sentence in sentences:
            sentence = _clean_name(re.sub(r"^(?:事件|剧情|发生)[:：]\s*", "", sentence))
            if any(marker in sentence for marker in ("发现", "遭遇", "决定", "战斗", "逃离", "抵达", "失踪", "爆发", "响", "打开", "求救", "关门", "闪过", "传来")):
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
        if entity.get("attributes"):
            item["attributes"] = entity["attributes"]
        if entity["entity_type"] == "character":
            sections["character_rules"].append(item)
        elif entity["entity_type"] == "scene":
            sections["scene_rules"].append(item)
        elif entity["entity_type"] == "prop":
            sections["prop_rules"].append(item)
        elif entity["entity_type"] == "event":
            sections["event_timeline"].append({"title": entity["name"], **item})
    return sections
