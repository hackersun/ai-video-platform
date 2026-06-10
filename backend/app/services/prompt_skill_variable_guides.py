"""Standard variable guides for Prompt skill editing and preview."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional


TASK_LABELS: Dict[str, str] = {
    "novel_generation": "小说创建",
    "chapter_writing": "章节创建",
    "script_generation": "剧本创建",
    "storyboard_generation": "分镜创建",
    "entity_extraction": "实体/资产抽取",
    "shot_prompt": "镜头创建",
    "shot_video": "镜头视频",
    "character_image": "头像/角色图",
    "scene_reference_image": "场景图",
    "prop_image": "道具图",
    "novel_cover": "封面图",
    "tts_dialogue": "角色配音",
    "shot_audio_video": "音视频直生",
    "consistency_review": "一致性审查",
    "repair_suggestion": "返修建议",
}


def _var(
    name: str,
    label: str,
    description: str,
    example: Any,
    *,
    source: str = "系统上下文",
    system_fill: bool = True,
    required: bool = False,
    aliases: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "name": name,
        "label": label,
        "description": description,
        "example": example,
        "source": source,
        "system_fill": system_fill,
        "required": required,
        "aliases": aliases or [],
    }


COMMON_VARIABLES: List[Dict[str, Any]] = [
    _var("title", "标题", "当前小说、章节、剧本、分镜或资产任务标题。", "雾港铜铃"),
    _var("genre", "题材", "当前作品或生成入口选择的题材类型。", "悬疑短剧"),
    _var("style", "风格", "当前入口选择的画风、写作风格或生成风格。", "电影感动漫"),
    _var("description", "简介/说明", "当前作品、角色、资产或任务说明。", "沈砚追查密信失踪，旧码头再次响起铜铃。"),
    _var("prompt", "用户提示词", "用户在生成入口填写的原始提示词或补充要求。", "突出雨夜旧码头的悬疑感"),
    _var("user_prompt", "用户补充提示", "封面、图像或视频生成入口的补充提示。", "冷色月光、铜铃特写"),
]


TASK_VARIABLES: Dict[str, List[Dict[str, Any]]] = {
    "novel_generation": [
        _var("theme", "主题", "小说创建入口的核心创意，可用 prompt 或中文变量“主题”承接。", "星海试炼", aliases=["主题"]),
        _var("chapter_count", "章节数量", "小说生成时请求的章节数。", 6, aliases=["章节数量"]),
        _var("audience", "目标受众", "内置模板默认变量，系统未传时使用技能默认值。", "短剧观众", source="模板默认值", system_fill=False),
        _var("episode_count", "目标集数", "内置模板默认变量，系统未传时使用技能默认值。", 12, source="模板默认值", system_fill=False),
    ],
    "chapter_writing": [
        _var("chapter_title", "章节标题", "当前章节标题或计划标题。", "第一章 雨夜铜铃"),
        _var("chapter_goal", "章节目标", "本章要完成的剧情推进目标。", "推进主线冲突"),
        _var("previous_summary", "前情摘要", "前一章节或 Story Bible 连续性摘要。", "密信失踪，沈砚锁定旧码头。"),
        _var("chapter_outline", "章节大纲", "章节创建或润色时的结构草稿。", "开场钩子-追查线索-章尾悬念"),
        _var("source_content", "来源内容", "章节改写、续写或拆分时的原始内容。", "沈砚听见铜铃声，从雨幕里走向旧码头。"),
    ],
    "script_generation": [
        _var("content", "剧本正文", "当前剧本正文或待润色内容。", "沈砚来到旧码头。\n沈砚：铜铃声就在码头尽头。"),
        _var("mode", "辅助模式", "剧本 AI 辅助模式，如 polish_content、short_drama。", "polish_content"),
        _var("format", "剧本格式", "内置模板默认变量，系统未传时使用技能默认值。", "分场剧本", source="模板默认值", system_fill=False),
        _var("duration", "目标时长", "剧本或短剧目标时长。", "60-90秒"),
    ],
    "storyboard_generation": [
        _var("source_title", "来源标题", "用于分镜的小说、章节或剧本标题。", "雾港铜铃"),
        _var("script_title", "剧本标题", "普通分镜生成时绑定的剧本标题。", "雾港铜铃"),
        _var("source_content", "来源正文", "用于拆分镜头的剧本、小说或章节正文，会进入模型提示词。", "沈砚来到旧码头。\n沈砚：铜铃又响了。"),
        _var("shot_count", "镜头数量", "分镜生成入口指定或模板推断的镜头数量。", 8),
        _var(
            "dialogue",
            "对白/台词",
            "分镜和镜头中的台词字段，建议使用“角色名：台词”或“（旁白）台词”格式，后续会用于配音和字幕。",
            "沈砚：铜铃又响了。",
        ),
        _var(
            "subtitle_text",
            "字幕文本",
            "镜头 extra_data.subtitle_text 或 dialogue 的字幕文本，视频和字幕链路会优先读取。",
            "沈砚：铜铃又响了。",
        ),
        _var("dialogue_speaker", "说话人", "分镜 extra_data.dialogue_speaker，用于配音人声和字幕绑定。", "沈砚"),
        _var("template_name", "分镜模板", "智能分镜匹配到的模板名称。", "雨夜悬疑对白模板"),
    ],
    "entity_extraction": [
        _var("source_content", "来源正文", "用于抽取实体和资产候选的小说、章节、剧本或分镜文本。", "沈砚在雨夜旧码头听见铜铃声。"),
        _var("entity_types", "实体类型", "本次允许抽取的实体类型中文列表。", "character、scene、prop、event"),
        _var("allowed_entity_types", "允许类型", "本次允许抽取的实体类型英文列表。", "character, scene, prop, event"),
        _var("output_format", "输出格式", "抽取模型必须遵守的输出格式。", "JSON 数组"),
        _var("classification_rules", "分类规则", "可在自定义模板中补充角色、场景、道具、事件的分类边界。", "角色必须是单一个体，群体和情绪词不能作为角色。", source="模板默认值", system_fill=False),
    ],
    "shot_prompt": [
        _var("shot_number", "镜头编号", "当前镜头序号。", 3),
        _var("shot_prompt", "镜头提示词", "当前镜头的视频/图像核心描述。", "沈砚在旧码头停步，铜铃在雨中轻晃。"),
        _var("visual_description", "视觉描述", "镜头构图、光影、人物位置、动作细节。", "中景，冷色月光，沈砚侧脸被雨水打湿。"),
        _var("camera_angle", "机位", "镜头机位或景别。", "medium"),
        _var("camera_movement", "运镜", "镜头运动方式。", "轻微推进"),
        _var("dialogue", "对白/台词", "当前镜头台词，会影响字幕、配音和视频口型。", "沈砚：铜铃又响了。"),
        _var("subtitle_text", "字幕文本", "当前镜头字幕文本，通常来自 dialogue。", "沈砚：铜铃又响了。"),
        _var("aspect_ratio", "画幅比例", "镜头提示词目标画幅。", "9:16", source="模板默认值", system_fill=False),
        _var("tone", "色调", "镜头色彩或气氛倾向。", "冷蓝月光"),
    ],
    "shot_video": [
        _var("shot_id", "镜头ID", "当前生成视频绑定的镜头 ID。", "shot-001"),
        _var("shot_prompt", "镜头提示词", "当前镜头的视频生成核心描述。", "沈砚在雨夜旧码头看向铜铃。"),
        _var("dialogue", "对白/台词", "当前镜头 dialogue 字段，会用于字幕和有声视频约束。", "沈砚：铜铃又响了。"),
        _var("subtitle_text", "字幕文本", "当前镜头字幕文本，视频生成和字幕导出会使用。", "沈砚：铜铃又响了。"),
        _var("duration", "视频时长", "镜头视频生成时长。", "4秒"),
        _var("motion", "运镜动作", "视频生成时的主要运动方式。", "轻微推进"),
        _var("locked_assets", "锁定资产", "角色、场景、道具等资产锁摘要。", "沈砚头像、旧码头场景、铜铃道具"),
    ],
    "character_image": [
        _var("character_name", "角色姓名", "头像或角色图绑定的角色名。", "沈砚", aliases=["角色姓名"]),
        _var("character_description", "角色描述", "角色身份、设定和剧情定位。", "年轻密探，谨慎敏锐。"),
        _var("appearance", "外貌特征", "脸型、发型、服装、标志物等外观信息。", "黑发束起，深色短袍，佩铜铃。"),
        _var("personality", "性格气质", "角色性格和视觉气质。", "克制、敏锐、警觉"),
        _var("voice", "声音风格", "角色声音或语言风格，可辅助配音一致性。", "低沉清晰"),
        _var("view", "视图类型", "头像、半身、全身、多视图等角色资产类型。", "头像"),
    ],
    "scene_reference_image": [
        _var("scene_name", "场景名称", "场景资产名称。", "旧码头"),
        _var("scene_type", "场景类型", "主场景、室内、街道、战斗场等场景类型。", "主场景"),
        _var("environment", "环境描述", "空间结构、天气、时代、可行动区域。", "雨夜木栈道，远处有仓库和雾灯。"),
        _var("lighting", "光线", "场景光源和光影方向。", "冷色月光"),
    ],
    "prop_image": [
        _var("prop_name", "道具名称", "道具资产名称。", "裂纹铜铃"),
        _var("material", "材质", "道具材质、纹理和比例。", "金属与玉石"),
        _var("state", "状态", "道具破损、发光、使用状态。", "轻微发光"),
        _var("usage", "使用方式", "道具在剧情或镜头中的用途。", "用于提示密信位置"),
    ],
    "novel_cover": [
        _var("cover_focus", "封面焦点", "封面要突出的角色、场景或冲突。", "沈砚与雨夜铜铃"),
        _var("market_positioning", "商业定位", "封面面向的平台、风格和读者预期。", "竖版短剧封面，悬疑抓眼"),
    ],
    "tts_dialogue": [
        _var("character_name", "角色姓名", "当前配音角色名。", "沈砚"),
        _var("dialogue", "对白/台词", "待配音台词，建议短句并保留说话人。", "沈砚：铜铃又响了。"),
        _var("voice_style", "声音风格", "角色声音风格或 TTS 音色要求。", "清晰自然"),
        _var("emotion", "情绪", "当前台词情绪和强度。", "克制紧张"),
        _var("pause_hint", "停顿提示", "配音停顿、重音或节奏要求。", "铜铃后短暂停顿"),
    ],
    "shot_audio_video": [
        _var("shot_prompt", "镜头提示词", "有声视频生成的画面提示词。", "沈砚在雨夜旧码头看向铜铃。"),
        _var("dialogue", "对白/台词", "有声视频中的台词，需和口型/字幕同步。", "沈砚：铜铃又响了。"),
        _var("subtitle_text", "字幕文本", "字幕文本，通常和 dialogue 一致。", "沈砚：铜铃又响了。"),
        _var("duration", "视频时长", "有声视频目标时长。", "4秒"),
        _var("audio_mode", "音频策略", "对白优先、环境声优先等音频策略。", "对白优先"),
    ],
    "consistency_review": [
        _var("risk_focus", "风险重点", "本次审查要优先关注的问题类型。", "角色漂移、资产缺失、剧情断裂"),
        _var("current_state", "当前状态", "Story Bible 或生产合约中的当前人物、场景、道具状态。", "沈砚在旧码头，铜铃已裂。"),
        _var("test_mode", "测试模式", "是否允许测试跳过非关键阻断项。", "true"),
    ],
    "repair_suggestion": [
        _var("repair_depth", "修复深度", "返修建议采用的修复粒度。", "最小可行修复"),
        _var("issue_summary", "问题摘要", "一致性审查或生产前置检查发现的问题。", "镜头缺少字幕文本和说话人。"),
        _var("repair_entry", "修复入口", "推荐用户点击的页面或快捷动作。", "分镜详情-编辑镜头对白"),
    ],
}


def _merged_variables(task: str) -> List[Dict[str, Any]]:
    seen = set()
    items: List[Dict[str, Any]] = []
    for item in [*COMMON_VARIABLES, *TASK_VARIABLES.get(task, [])]:
        name = item["name"]
        if name in seen:
            continue
        seen.add(name)
        items.append(deepcopy(item))
    return items


def get_prompt_skill_variable_guide(task: str) -> Dict[str, Any]:
    items = _merged_variables(task)
    return {
        "task": task,
        "task_label": TASK_LABELS.get(task, task),
        "items": items,
        "sample_context": {item["name"]: item["example"] for item in items if item.get("example") is not None},
    }


def list_prompt_skill_variable_guides() -> Dict[str, Any]:
    guides = [get_prompt_skill_variable_guide(task) for task in TASK_LABELS]
    return {"items": guides, "count": len(guides)}
