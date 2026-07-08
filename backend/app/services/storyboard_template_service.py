"""
Storyboard template matching and draft shot generation.

Templates are deterministic production scaffolds: AI can refine them when a text
model is configured, while DEV_MODE can still create reviewable storyboards.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional


DEFAULT_SHOT_PATTERN: Dict[str, Any] = {
    "duration": 4,
    "shot_type": "detail",
    "camera_angle": "medium",
    "camera_movement": "static",
    "emotion": "neutral",
    "lighting": "natural",
    "color_grading": "cinematic",
    "visual_focus": "承接当前情节点，保持人物、场景和道具连续",
    "dialogue_role": "旁白",
}


STORYBOARD_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "anime-dialogue",
        "name": "动画对话场景",
        "description": "两人或多人互动，正反打与反应镜头为主。",
        "genre_tags": ["动画", "言情", "都市", "日常", "对话"],
        "keywords": ["说", "问", "回答", "沉默", "对话", "看着", "解释", "争论"],
        "shots": [
            {"duration": 4, "shot_type": "establishing", "camera_angle": "wide", "camera_movement": "static", "emotion": "neutral", "lighting": "natural", "color_grading": "cinematic", "visual_focus": "交代人物所在场景和空间关系", "dialogue_role": "旁白"},
            {"duration": 4, "shot_type": "dialogue", "camera_angle": "close-up", "camera_movement": "static", "emotion": "tense", "lighting": "soft", "color_grading": "warm", "visual_focus": "主说话人的表情和眼神", "dialogue_role": "角色"},
            {"duration": 3, "shot_type": "reaction", "camera_angle": "over-shoulder", "camera_movement": "pan_left", "emotion": "surprised", "lighting": "soft", "color_grading": "cinematic", "visual_focus": "对方的反应和微动作", "dialogue_role": "角色"},
            {"duration": 4, "shot_type": "dialogue", "camera_angle": "two-shot", "camera_movement": "zoom_in", "emotion": "tense", "lighting": "dramatic", "color_grading": "warm", "visual_focus": "两人关系变化和情绪推进", "dialogue_role": "角色"},
            {"duration": 5, "shot_type": "summary", "camera_angle": "wide", "camera_movement": "zoom_out", "emotion": "neutral", "lighting": "golden_hour", "color_grading": "cinematic", "visual_focus": "对话后的环境变化和余韵", "dialogue_role": "旁白"},
        ],
    },
    {
        "id": "action-sequence",
        "name": "动作追逐/战斗",
        "description": "战斗、逃亡、追逐等高强度场景，短镜头和动态运镜。",
        "genre_tags": ["动作", "玄幻", "仙侠", "奇幻", "科幻", "战斗"],
        "keywords": ["战", "剑", "追", "逃", "杀", "爆", "冲", "击", "拳", "刀", "伏击", "奔"],
        "shots": [
            {"duration": 3, "shot_type": "establishing", "camera_angle": "wide", "camera_movement": "zoom_in", "emotion": "tense", "lighting": "dramatic", "color_grading": "cool", "visual_focus": "战斗场地、双方位置和危险源", "dialogue_role": "旁白"},
            {"duration": 3, "shot_type": "action", "camera_angle": "tracking", "camera_movement": "handheld", "emotion": "tense", "lighting": "dramatic", "color_grading": "vibrant", "visual_focus": "主角高速移动和躲闪", "dialogue_role": None},
            {"duration": 2, "shot_type": "action", "camera_angle": "extreme-close-up", "camera_movement": "zoom_in", "emotion": "angry", "lighting": "rim", "color_grading": "vibrant", "visual_focus": "武器、拳脚或关键动作瞬间", "dialogue_role": None},
            {"duration": 3, "shot_type": "reaction", "camera_angle": "medium", "camera_movement": "pan_right", "emotion": "surprised", "lighting": "back", "color_grading": "cool", "visual_focus": "敌我双方的反应和局势变化", "dialogue_role": "角色"},
            {"duration": 5, "shot_type": "summary", "camera_angle": "aerial", "camera_movement": "crane", "emotion": "excited", "lighting": "dramatic", "color_grading": "cinematic", "visual_focus": "高潮动作和场景破坏结果", "dialogue_role": "旁白"},
        ],
    },
    {
        "id": "emotional-scene",
        "name": "情感抒情场景",
        "description": "离别、回忆、告白、内心独白等慢节奏情绪表达。",
        "genre_tags": ["情感", "言情", "治愈", "虐心", "回忆"],
        "keywords": ["泪", "哭", "想起", "回忆", "离开", "孤独", "心", "告别", "沉默", "遗憾"],
        "shots": [
            {"duration": 5, "shot_type": "establishing", "camera_angle": "wide", "camera_movement": "static", "emotion": "sad", "lighting": "golden_hour", "color_grading": "desaturated", "visual_focus": "空旷环境和角色孤立感", "dialogue_role": "旁白"},
            {"duration": 6, "shot_type": "reaction", "camera_angle": "close-up", "camera_movement": "zoom_in", "emotion": "sad", "lighting": "soft", "color_grading": "warm", "visual_focus": "角色面部细微情绪和眼神", "dialogue_role": "角色"},
            {"duration": 4, "shot_type": "detail", "camera_angle": "extreme-close-up", "camera_movement": "static", "emotion": "tense", "lighting": "rim", "color_grading": "vintage", "visual_focus": "关键道具、手部动作或记忆线索", "dialogue_role": None},
            {"duration": 7, "shot_type": "summary", "camera_angle": "long-shot", "camera_movement": "zoom_out", "emotion": "relaxed", "lighting": "moonlight", "color_grading": "cinematic", "visual_focus": "情绪释放后的背影和环境余韵", "dialogue_role": "旁白"},
        ],
    },
    {
        "id": "montage-growth",
        "name": "成长训练蒙太奇",
        "description": "训练、时间流逝、信息快速铺陈，多个短镜头串联。",
        "genre_tags": ["成长", "修炼", "训练", "通用"],
        "keywords": ["训练", "修炼", "多年", "日复一日", "成长", "变化", "练习", "时间"],
        "shots": [
            {"duration": 2, "shot_type": "montage", "camera_angle": "close-up", "camera_movement": "static", "emotion": "tense", "lighting": "natural", "color_grading": "warm", "visual_focus": "训练开始的第一处细节", "dialogue_role": "旁白"},
            {"duration": 2, "shot_type": "montage", "camera_angle": "medium", "camera_movement": "pan_left", "emotion": "neutral", "lighting": "dramatic", "color_grading": "vibrant", "visual_focus": "重复动作和节奏变化", "dialogue_role": None},
            {"duration": 2, "shot_type": "montage", "camera_angle": "extreme-close-up", "camera_movement": "zoom_in", "emotion": "excited", "lighting": "rim", "color_grading": "vibrant", "visual_focus": "突破瞬间或关键能力显现", "dialogue_role": None},
            {"duration": 4, "shot_type": "summary", "camera_angle": "wide", "camera_movement": "zoom_out", "emotion": "excited", "lighting": "golden_hour", "color_grading": "cinematic", "visual_focus": "训练成果和新的目标", "dialogue_role": "旁白"},
        ],
    },
    {
        "id": "mystery-reveal",
        "name": "悬疑揭示场景",
        "description": "发现线索、秘密揭晓、阴谋推进，注重低光和细节。",
        "genre_tags": ["悬疑", "推理", "惊悚", "秘密"],
        "keywords": ["线索", "秘密", "发现", "真相", "疑", "暗", "门", "血", "影", "低声"],
        "shots": [
            {"duration": 4, "shot_type": "establishing", "camera_angle": "wide", "camera_movement": "static", "emotion": "tense", "lighting": "moonlight", "color_grading": "noir", "visual_focus": "低光环境和不安氛围", "dialogue_role": "旁白"},
            {"duration": 3, "shot_type": "detail", "camera_angle": "extreme-close-up", "camera_movement": "zoom_in", "emotion": "surprised", "lighting": "rim", "color_grading": "noir", "visual_focus": "关键线索或异常道具", "dialogue_role": None},
            {"duration": 4, "shot_type": "reaction", "camera_angle": "close-up", "camera_movement": "handheld", "emotion": "tense", "lighting": "dramatic", "color_grading": "cool", "visual_focus": "角色意识到真相的表情", "dialogue_role": "角色"},
            {"duration": 5, "shot_type": "transition", "camera_angle": "over-shoulder", "camera_movement": "zoom_out", "emotion": "tense", "lighting": "back", "color_grading": "cinematic", "visual_focus": "秘密背后的更大危险", "dialogue_role": "旁白"},
        ],
    },
    {
        "id": "world-establishing",
        "name": "世界观展示",
        "description": "展示城市、宗门、星港、异世界等宏观环境。",
        "genre_tags": ["玄幻", "仙侠", "科幻", "奇幻", "历史", "世界观"],
        "keywords": ["城", "宗门", "星港", "王朝", "世界", "山", "海", "云", "宫", "基地", "飞船"],
        "shots": [
            {"duration": 6, "shot_type": "establishing", "camera_angle": "aerial", "camera_movement": "crane", "emotion": "neutral", "lighting": "golden_hour", "color_grading": "cinematic", "visual_focus": "宏观环境、地标和时代气质", "dialogue_role": "旁白"},
            {"duration": 5, "shot_type": "detail", "camera_angle": "wide", "camera_movement": "pan_right", "emotion": "neutral", "lighting": "natural", "color_grading": "vibrant", "visual_focus": "街道、人群、交通或宗门结构", "dialogue_role": None},
            {"duration": 4, "shot_type": "detail", "camera_angle": "medium", "camera_movement": "static", "emotion": "surprised", "lighting": "rim", "color_grading": "cinematic", "visual_focus": "主角与世界规则产生关联", "dialogue_role": "角色"},
            {"duration": 5, "shot_type": "summary", "camera_angle": "wide", "camera_movement": "zoom_out", "emotion": "excited", "lighting": "dramatic", "color_grading": "cinematic", "visual_focus": "世界规模和后续冒险方向", "dialogue_role": "旁白"},
        ],
    },
    {
        "id": "opening-hook",
        "name": "强钩子开场",
        "description": "首集或章节开头快速抛出悬念、危机或反常事件。",
        "genre_tags": ["通用", "开场", "悬念", "冒险", "爽文"],
        "keywords": ["突然", "醒来", "倒计时", "警报", "异变", "失踪", "坠落", "危机", "开局"],
        "shots": [
            {"duration": 4, "shot_type": "establishing", "camera_angle": "wide", "camera_movement": "zoom_in", "emotion": "tense", "lighting": "dramatic", "color_grading": "cinematic", "visual_focus": "用异常环境或危险信号建立开场冲突", "dialogue_role": "旁白"},
            {"duration": 4, "shot_type": "detail", "camera_angle": "extreme-close-up", "camera_movement": "static", "emotion": "surprised", "lighting": "rim", "color_grading": "cool", "visual_focus": "关键线索、倒计时、伤痕或异物细节", "dialogue_role": None},
            {"duration": 4, "shot_type": "reaction", "camera_angle": "close-up", "camera_movement": "handheld", "emotion": "tense", "lighting": "dramatic", "color_grading": "cinematic", "visual_focus": "主角意识到异常后的第一反应", "dialogue_role": "角色"},
            {"duration": 5, "shot_type": "transition", "camera_angle": "wide", "camera_movement": "zoom_out", "emotion": "tense", "lighting": "back", "color_grading": "noir", "visual_focus": "把问题扩大到后续剧情目标", "dialogue_role": "旁白"},
        ],
    },
    {
        "id": "character-entrance",
        "name": "主要人物登场",
        "description": "突出角色第一印象、身份气质、能力和关系张力。",
        "genre_tags": ["通用", "人物", "登场", "群像", "角色"],
        "keywords": ["出现", "走来", "登场", "抬头", "身份", "传闻", "目光", "初见"],
        "shots": [
            {"duration": 5, "shot_type": "establishing", "camera_angle": "wide", "camera_movement": "static", "emotion": "neutral", "lighting": "natural", "color_grading": "cinematic", "visual_focus": "角色登场前的空间和人群反应", "dialogue_role": "旁白"},
            {"duration": 4, "shot_type": "detail", "camera_angle": "close-up", "camera_movement": "pan_left", "emotion": "neutral", "lighting": "rim", "color_grading": "warm", "visual_focus": "服饰、发型、随身道具和视觉 DNA", "dialogue_role": None},
            {"duration": 4, "shot_type": "reaction", "camera_angle": "two-shot", "camera_movement": "zoom_in", "emotion": "surprised", "lighting": "soft", "color_grading": "cinematic", "visual_focus": "其他角色对其身份或气场的反应", "dialogue_role": "角色"},
            {"duration": 5, "shot_type": "summary", "camera_angle": "medium", "camera_movement": "static", "emotion": "tense", "lighting": "dramatic", "color_grading": "cinematic", "visual_focus": "用一句行动或台词锁定人物目标", "dialogue_role": "角色"},
        ],
    },
    {
        "id": "group-briefing",
        "name": "群像会议/任务简报",
        "description": "多人围绕任务、线索、计划或阵营分歧展开信息同步。",
        "genre_tags": ["通用", "群像", "任务", "会议", "策略"],
        "keywords": ["会议", "计划", "任务", "地图", "简报", "目标", "分工", "讨论", "队伍"],
        "shots": [
            {"duration": 5, "shot_type": "establishing", "camera_angle": "wide", "camera_movement": "static", "emotion": "neutral", "lighting": "natural", "color_grading": "cinematic", "visual_focus": "交代会议空间、座位关系和任务核心物", "dialogue_role": "旁白"},
            {"duration": 4, "shot_type": "detail", "camera_angle": "over-shoulder", "camera_movement": "zoom_in", "emotion": "tense", "lighting": "soft", "color_grading": "cool", "visual_focus": "地图、文件、终端或关键道具上的目标信息", "dialogue_role": None},
            {"duration": 4, "shot_type": "dialogue", "camera_angle": "medium", "camera_movement": "pan_right", "emotion": "tense", "lighting": "dramatic", "color_grading": "cinematic", "visual_focus": "核心人物提出方案或风险", "dialogue_role": "角色"},
            {"duration": 4, "shot_type": "reaction", "camera_angle": "two-shot", "camera_movement": "static", "emotion": "surprised", "lighting": "soft", "color_grading": "warm", "visual_focus": "队友分歧、沉默或态度变化", "dialogue_role": "角色"},
            {"duration": 5, "shot_type": "summary", "camera_angle": "wide", "camera_movement": "zoom_out", "emotion": "tense", "lighting": "back", "color_grading": "cinematic", "visual_focus": "任务分工确定并引向下一场行动", "dialogue_role": "旁白"},
        ],
    },
    {
        "id": "villain-pressure",
        "name": "反派压迫/危机降临",
        "description": "强化敌方威胁、压迫感、倒计时和主角处境。",
        "genre_tags": ["反派", "危机", "压迫", "战斗", "悬疑"],
        "keywords": ["反派", "敌人", "威胁", "压迫", "冷笑", "包围", "陷阱", "审判", "黑影"],
        "shots": [
            {"duration": 4, "shot_type": "establishing", "camera_angle": "low-angle", "camera_movement": "zoom_in", "emotion": "tense", "lighting": "dramatic", "color_grading": "noir", "visual_focus": "敌方登场或压迫空间形成", "dialogue_role": "旁白"},
            {"duration": 4, "shot_type": "detail", "camera_angle": "extreme-close-up", "camera_movement": "static", "emotion": "angry", "lighting": "rim", "color_grading": "cool", "visual_focus": "反派眼神、武器、徽记或控制装置", "dialogue_role": None},
            {"duration": 4, "shot_type": "dialogue", "camera_angle": "close-up", "camera_movement": "zoom_in", "emotion": "tense", "lighting": "dramatic", "color_grading": "noir", "visual_focus": "反派用台词揭示威胁或筹码", "dialogue_role": "角色"},
            {"duration": 5, "shot_type": "reaction", "camera_angle": "medium", "camera_movement": "handheld", "emotion": "surprised", "lighting": "back", "color_grading": "cinematic", "visual_focus": "主角或同伴被迫做出选择", "dialogue_role": "角色"},
        ],
    },
    {
        "id": "rescue-turnaround",
        "name": "危机救援/逆转",
        "description": "绝境中出现救援、能力爆发或策略反制，形成爽点逆转。",
        "genre_tags": ["救援", "逆转", "动作", "热血", "爽文"],
        "keywords": ["救", "挡住", "反击", "逆转", "赶到", "爆发", "护住", "翻盘", "机会"],
        "shots": [
            {"duration": 4, "shot_type": "reaction", "camera_angle": "close-up", "camera_movement": "handheld", "emotion": "tense", "lighting": "dramatic", "color_grading": "cool", "visual_focus": "危机即将落下时的绝望反应", "dialogue_role": "角色"},
            {"duration": 3, "shot_type": "action", "camera_angle": "tracking", "camera_movement": "zoom_in", "emotion": "excited", "lighting": "rim", "color_grading": "vibrant", "visual_focus": "救援者切入、技能启动或关键道具介入", "dialogue_role": None},
            {"duration": 4, "shot_type": "action", "camera_angle": "wide", "camera_movement": "pan_right", "emotion": "excited", "lighting": "dramatic", "color_grading": "vibrant", "visual_focus": "局势反转的连续动作和空间变化", "dialogue_role": None},
            {"duration": 5, "shot_type": "summary", "camera_angle": "two-shot", "camera_movement": "zoom_out", "emotion": "relaxed", "lighting": "golden_hour", "color_grading": "cinematic", "visual_focus": "逆转后的关系变化和新的代价", "dialogue_role": "角色"},
        ],
    },
    {
        "id": "cliffhanger-ending",
        "name": "结尾悬念/下集钩子",
        "description": "一集或一章结尾留下信息反转、未知敌人或未完成选择。",
        "genre_tags": ["通用", "结尾", "悬念", "反转", "下集"],
        "keywords": ["结尾", "忽然", "最后", "背后", "真相", "打开", "来不及", "未完", "下集"],
        "shots": [
            {"duration": 5, "shot_type": "summary", "camera_angle": "wide", "camera_movement": "zoom_out", "emotion": "neutral", "lighting": "golden_hour", "color_grading": "cinematic", "visual_focus": "当前事件看似落定后的静场", "dialogue_role": "旁白"},
            {"duration": 4, "shot_type": "detail", "camera_angle": "extreme-close-up", "camera_movement": "zoom_in", "emotion": "surprised", "lighting": "rim", "color_grading": "cool", "visual_focus": "突然出现的新线索、信息或异动", "dialogue_role": None},
            {"duration": 4, "shot_type": "reaction", "camera_angle": "close-up", "camera_movement": "static", "emotion": "tense", "lighting": "dramatic", "color_grading": "cinematic", "visual_focus": "角色意识到更大问题后的表情", "dialogue_role": "角色"},
            {"duration": 5, "shot_type": "transition", "camera_angle": "wide", "camera_movement": "zoom_out", "emotion": "tense", "lighting": "moonlight", "color_grading": "noir", "visual_focus": "用未知人物、远景或声音引出下一集", "dialogue_role": "旁白"},
        ],
    },
    {
        "id": "comedy-daily-beat",
        "name": "日常喜剧节奏",
        "description": "轻松日常、误会、吐槽和反差包袱，适合中低强度剧情。",
        "genre_tags": ["日常", "喜剧", "校园", "轻松", "治愈"],
        "keywords": ["误会", "吐槽", "尴尬", "笑", "日常", "饭", "课堂", "摔倒", "夸张"],
        "shots": [
            {"duration": 4, "shot_type": "establishing", "camera_angle": "wide", "camera_movement": "static", "emotion": "relaxed", "lighting": "natural", "color_grading": "warm", "visual_focus": "轻松环境和人物日常状态", "dialogue_role": "旁白"},
            {"duration": 4, "shot_type": "dialogue", "camera_angle": "two-shot", "camera_movement": "pan_left", "emotion": "surprised", "lighting": "soft", "color_grading": "warm", "visual_focus": "误会或反差包袱形成", "dialogue_role": "角色"},
            {"duration": 3, "shot_type": "reaction", "camera_angle": "close-up", "camera_movement": "zoom_in", "emotion": "surprised", "lighting": "natural", "color_grading": "vibrant", "visual_focus": "夸张表情、停顿和喜剧反应", "dialogue_role": "角色"},
            {"duration": 4, "shot_type": "summary", "camera_angle": "medium", "camera_movement": "zoom_out", "emotion": "relaxed", "lighting": "natural", "color_grading": "warm", "visual_focus": "包袱落地后恢复关系和节奏", "dialogue_role": "旁白"},
        ],
    },
    {
        "id": "investigation-process",
        "name": "调查推理过程",
        "description": "角色调查线索、验证假设、串联证据并逼近真相。",
        "genre_tags": ["悬疑", "推理", "调查", "刑侦", "解谜"],
        "keywords": ["调查", "证据", "推理", "线索", "现场", "痕迹", "证词", "疑点", "档案"],
        "shots": [
            {"duration": 5, "shot_type": "establishing", "camera_angle": "wide", "camera_movement": "static", "emotion": "tense", "lighting": "natural", "color_grading": "cool", "visual_focus": "调查现场、空间关系和可疑区域", "dialogue_role": "旁白"},
            {"duration": 4, "shot_type": "detail", "camera_angle": "extreme-close-up", "camera_movement": "zoom_in", "emotion": "surprised", "lighting": "rim", "color_grading": "noir", "visual_focus": "证据细节、痕迹或异常道具", "dialogue_role": None},
            {"duration": 4, "shot_type": "dialogue", "camera_angle": "over-shoulder", "camera_movement": "static", "emotion": "tense", "lighting": "soft", "color_grading": "cool", "visual_focus": "角色用台词串联疑点和假设", "dialogue_role": "角色"},
            {"duration": 5, "shot_type": "transition", "camera_angle": "medium", "camera_movement": "zoom_out", "emotion": "tense", "lighting": "dramatic", "color_grading": "cinematic", "visual_focus": "证据指向下一处人物或场景", "dialogue_role": "旁白"},
        ],
    },
    {
        "id": "xianxia-breakthrough",
        "name": "修仙突破/雷劫",
        "description": "灵气汇聚、境界突破、雷劫压迫和法宝护体，适合修仙爽点。",
        "genre_tags": ["修仙", "仙侠", "突破", "雷劫", "宗门", "修炼"],
        "keywords": ["修炼", "突破", "境界", "灵气", "灵根", "金丹", "元婴", "雷劫", "渡劫", "丹田", "法宝", "护体"],
        "shots": [
            {"duration": 5, "shot_type": "establishing", "camera_angle": "aerial", "camera_movement": "crane", "emotion": "tense", "lighting": "moonlight", "color_grading": "cool", "visual_focus": "洞府、山门或云海上方灵气旋涡形成", "dialogue_role": "旁白"},
            {"duration": 4, "shot_type": "detail", "camera_angle": "extreme-close-up", "camera_movement": "zoom_in", "emotion": "tense", "lighting": "rim", "color_grading": "vibrant", "visual_focus": "丹田、灵根、符文或法宝开始发光", "dialogue_role": None},
            {"duration": 5, "shot_type": "reaction", "camera_angle": "close-up", "camera_movement": "handheld", "emotion": "excited", "lighting": "dramatic", "color_grading": "cinematic", "visual_focus": "主角承受雷劫压迫但眼神坚定", "dialogue_role": "角色"},
            {"duration": 4, "shot_type": "action", "camera_angle": "wide", "camera_movement": "zoom_in", "emotion": "angry", "lighting": "dramatic", "color_grading": "vibrant", "visual_focus": "雷光劈落、法宝护体、灵气爆发", "dialogue_role": None},
            {"duration": 5, "shot_type": "summary", "camera_angle": "wide", "camera_movement": "zoom_out", "emotion": "excited", "lighting": "golden_hour", "color_grading": "cinematic", "visual_focus": "突破成功后的气息变化和宗门震动", "dialogue_role": "旁白"},
        ],
    },
    {
        "id": "xianxia-sect-trial",
        "name": "宗门审判/大殿对峙",
        "description": "宗门大殿、长老威压、同门质疑和身份反转。",
        "genre_tags": ["修仙", "仙侠", "宗门", "审判", "师徒", "大殿"],
        "keywords": ["宗门", "长老", "掌门", "师尊", "同门", "审判", "戒律堂", "山门", "大殿", "逐出", "弟子"],
        "shots": [
            {"duration": 5, "shot_type": "establishing", "camera_angle": "wide", "camera_movement": "static", "emotion": "tense", "lighting": "dramatic", "color_grading": "cinematic", "visual_focus": "宗门大殿高台、长老席和弟子队列", "dialogue_role": "旁白"},
            {"duration": 4, "shot_type": "dialogue", "camera_angle": "low-angle", "camera_movement": "zoom_in", "emotion": "tense", "lighting": "rim", "color_grading": "cool", "visual_focus": "掌门或长老释放威压并质问主角", "dialogue_role": "角色"},
            {"duration": 4, "shot_type": "reaction", "camera_angle": "two-shot", "camera_movement": "pan_right", "emotion": "surprised", "lighting": "soft", "color_grading": "cinematic", "visual_focus": "同门议论、师徒关系和阵营分歧", "dialogue_role": "角色"},
            {"duration": 4, "shot_type": "detail", "camera_angle": "extreme-close-up", "camera_movement": "static", "emotion": "surprised", "lighting": "rim", "color_grading": "vibrant", "visual_focus": "身份玉牌、命灯、灵契或证据法器显现真相", "dialogue_role": None},
            {"duration": 5, "shot_type": "transition", "camera_angle": "wide", "camera_movement": "zoom_out", "emotion": "tense", "lighting": "back", "color_grading": "cinematic", "visual_focus": "审判结果引出下一场试炼或追杀", "dialogue_role": "旁白"},
        ],
    },
    {
        "id": "wuxia-jianghu-duel",
        "name": "武侠江湖对决",
        "description": "客栈、擂台、竹林或山道中的刀剑交锋与侠义抉择。",
        "genre_tags": ["武侠", "江湖", "刀剑", "门派", "侠义", "比武"],
        "keywords": ["江湖", "侠", "门派", "掌法", "剑法", "刀光", "轻功", "客栈", "擂台", "武林", "秘籍", "镖局"],
        "shots": [
            {"duration": 5, "shot_type": "establishing", "camera_angle": "wide", "camera_movement": "static", "emotion": "tense", "lighting": "golden_hour", "color_grading": "warm", "visual_focus": "客栈、竹林、擂台或山道交代江湖空间", "dialogue_role": "旁白"},
            {"duration": 4, "shot_type": "detail", "camera_angle": "extreme-close-up", "camera_movement": "zoom_in", "emotion": "tense", "lighting": "rim", "color_grading": "cinematic", "visual_focus": "刀剑出鞘、酒杯震动或秘籍露出一角", "dialogue_role": None},
            {"duration": 4, "shot_type": "dialogue", "camera_angle": "two-shot", "camera_movement": "pan_left", "emotion": "tense", "lighting": "soft", "color_grading": "warm", "visual_focus": "双方报出门派恩怨和侠义立场", "dialogue_role": "角色"},
            {"duration": 4, "shot_type": "action", "camera_angle": "tracking", "camera_movement": "handheld", "emotion": "excited", "lighting": "dramatic", "color_grading": "vibrant", "visual_focus": "轻功腾挪、刀剑交击和身法变化", "dialogue_role": None},
            {"duration": 5, "shot_type": "summary", "camera_angle": "medium", "camera_movement": "zoom_out", "emotion": "tense", "lighting": "back", "color_grading": "cinematic", "visual_focus": "胜负之外留下门派秘密或新恩怨", "dialogue_role": "旁白"},
        ],
    },
    {
        "id": "wuxia-night-infiltration",
        "name": "武侠夜探门派",
        "description": "飞檐走壁、暗哨、密室线索和门派阴谋揭示。",
        "genre_tags": ["武侠", "夜探", "门派", "轻功", "密室", "江湖"],
        "keywords": ["夜探", "潜入", "暗哨", "密室", "飞檐", "轻功", "山庄", "门派", "账册", "令牌", "机关"],
        "shots": [
            {"duration": 5, "shot_type": "establishing", "camera_angle": "aerial", "camera_movement": "crane", "emotion": "tense", "lighting": "moonlight", "color_grading": "noir", "visual_focus": "夜色中的门派山庄、屋脊和巡逻路线", "dialogue_role": "旁白"},
            {"duration": 4, "shot_type": "action", "camera_angle": "tracking", "camera_movement": "handheld", "emotion": "tense", "lighting": "moonlight", "color_grading": "cool", "visual_focus": "角色飞檐走壁避开暗哨", "dialogue_role": None},
            {"duration": 4, "shot_type": "detail", "camera_angle": "extreme-close-up", "camera_movement": "zoom_in", "emotion": "surprised", "lighting": "rim", "color_grading": "noir", "visual_focus": "机关锁、密信、令牌或账册证据", "dialogue_role": None},
            {"duration": 4, "shot_type": "reaction", "camera_angle": "close-up", "camera_movement": "static", "emotion": "surprised", "lighting": "dramatic", "color_grading": "cool", "visual_focus": "角色发现门派阴谋后的压低呼吸", "dialogue_role": "角色"},
            {"duration": 5, "shot_type": "transition", "camera_angle": "wide", "camera_movement": "zoom_out", "emotion": "tense", "lighting": "back", "color_grading": "noir", "visual_focus": "暗处敌人出现，夜探转为追逐", "dialogue_role": "旁白"},
        ],
    },
    {
        "id": "xuanhuan-secret-realm",
        "name": "玄幻秘境探索",
        "description": "古遗迹、异兽、神器线索和未知规则，适合玄幻冒险。",
        "genre_tags": ["玄幻", "秘境", "神器", "异兽", "遗迹", "血脉"],
        "keywords": ["玄幻", "秘境", "遗迹", "神器", "异兽", "血脉", "圣地", "古碑", "祭坛", "灵核", "禁地", "兽潮"],
        "shots": [
            {"duration": 6, "shot_type": "establishing", "camera_angle": "aerial", "camera_movement": "crane", "emotion": "surprised", "lighting": "golden_hour", "color_grading": "vibrant", "visual_focus": "巨型遗迹、浮空石阶、异兽剪影和秘境入口", "dialogue_role": "旁白"},
            {"duration": 4, "shot_type": "detail", "camera_angle": "wide", "camera_movement": "pan_right", "emotion": "neutral", "lighting": "rim", "color_grading": "cinematic", "visual_focus": "古碑符号、祭坛纹路和神器气息", "dialogue_role": None},
            {"duration": 4, "shot_type": "reaction", "camera_angle": "medium", "camera_movement": "handheld", "emotion": "tense", "lighting": "dramatic", "color_grading": "cool", "visual_focus": "队伍察觉秘境规则或异兽逼近", "dialogue_role": "角色"},
            {"duration": 4, "shot_type": "action", "camera_angle": "tracking", "camera_movement": "zoom_in", "emotion": "excited", "lighting": "dramatic", "color_grading": "vibrant", "visual_focus": "异兽突袭、元素能量和血脉防御显现", "dialogue_role": None},
            {"duration": 5, "shot_type": "summary", "camera_angle": "wide", "camera_movement": "zoom_out", "emotion": "tense", "lighting": "back", "color_grading": "cinematic", "visual_focus": "神器线索指向更深层秘境", "dialogue_role": "旁白"},
        ],
    },
    {
        "id": "xuanhuan-bloodline-awakening",
        "name": "玄幻血脉觉醒",
        "description": "血脉、灵核、族纹或天赋显现，形成角色能力爽点。",
        "genre_tags": ["玄幻", "血脉", "觉醒", "灵核", "天赋", "异能"],
        "keywords": ["血脉", "觉醒", "族纹", "灵核", "天赋", "血色", "神纹", "异象", "封印", "传承"],
        "shots": [
            {"duration": 4, "shot_type": "detail", "camera_angle": "extreme-close-up", "camera_movement": "zoom_in", "emotion": "tense", "lighting": "rim", "color_grading": "vibrant", "visual_focus": "掌心、瞳孔、族纹或灵核出现异光", "dialogue_role": None},
            {"duration": 5, "shot_type": "reaction", "camera_angle": "close-up", "camera_movement": "handheld", "emotion": "surprised", "lighting": "dramatic", "color_grading": "cool", "visual_focus": "主角痛苦或震惊，压制体内力量", "dialogue_role": "角色"},
            {"duration": 4, "shot_type": "establishing", "camera_angle": "wide", "camera_movement": "zoom_out", "emotion": "tense", "lighting": "dramatic", "color_grading": "vibrant", "visual_focus": "周围环境被血脉异象照亮", "dialogue_role": "旁白"},
            {"duration": 4, "shot_type": "action", "camera_angle": "medium", "camera_movement": "zoom_in", "emotion": "excited", "lighting": "rim", "color_grading": "vibrant", "visual_focus": "觉醒力量第一次改变战局或打开封印", "dialogue_role": None},
            {"duration": 5, "shot_type": "transition", "camera_angle": "close-up", "camera_movement": "static", "emotion": "tense", "lighting": "back", "color_grading": "cinematic", "visual_focus": "旁人认出血脉来历并埋下追杀风险", "dialogue_role": "角色"},
        ],
    },
    {
        "id": "urban-power-awakening",
        "name": "都市异能觉醒",
        "description": "现代城市中能力突然显现，适合短剧开场和主线引爆。",
        "genre_tags": ["都市", "都市异能", "现代", "异能", "校园", "超自然"],
        "keywords": ["都市", "异能", "觉醒", "手机", "监控", "地铁", "学校", "公司", "医院", "夜巷", "实验室", "组织"],
        "shots": [
            {"duration": 4, "shot_type": "establishing", "camera_angle": "wide", "camera_movement": "static", "emotion": "neutral", "lighting": "neon", "color_grading": "cool", "visual_focus": "现代城市、校园、公司或地铁的日常环境", "dialogue_role": "旁白"},
            {"duration": 4, "shot_type": "detail", "camera_angle": "extreme-close-up", "camera_movement": "zoom_in", "emotion": "surprised", "lighting": "rim", "color_grading": "vibrant", "visual_focus": "手机、监控、手表或瞳孔出现异常数据/能量", "dialogue_role": None},
            {"duration": 4, "shot_type": "reaction", "camera_angle": "close-up", "camera_movement": "handheld", "emotion": "surprised", "lighting": "neon", "color_grading": "cool", "visual_focus": "主角第一次意识到能力失控", "dialogue_role": "角色"},
            {"duration": 4, "shot_type": "action", "camera_angle": "tracking", "camera_movement": "zoom_in", "emotion": "tense", "lighting": "dramatic", "color_grading": "vibrant", "visual_focus": "异能短暂爆发，影响周围物体或人群", "dialogue_role": None},
            {"duration": 5, "shot_type": "transition", "camera_angle": "over-shoulder", "camera_movement": "zoom_out", "emotion": "tense", "lighting": "back", "color_grading": "noir", "visual_focus": "隐藏组织通过监控锁定主角", "dialogue_role": "旁白"},
        ],
    },
    {
        "id": "urban-night-chase",
        "name": "都市夜巷追查",
        "description": "现代城市夜景、追逐、监控线索和隐藏组织压迫。",
        "genre_tags": ["都市", "都市异能", "夜巷", "追逐", "悬疑", "现代"],
        "keywords": ["夜巷", "追查", "追逐", "监控", "地铁", "雨夜", "组织", "线索", "车灯", "霓虹", "实验室"],
        "shots": [
            {"duration": 4, "shot_type": "establishing", "camera_angle": "wide", "camera_movement": "zoom_in", "emotion": "tense", "lighting": "neon", "color_grading": "cool", "visual_focus": "雨后夜巷、霓虹反光和追逐路线", "dialogue_role": "旁白"},
            {"duration": 4, "shot_type": "action", "camera_angle": "tracking", "camera_movement": "handheld", "emotion": "tense", "lighting": "neon", "color_grading": "vibrant", "visual_focus": "角色穿过巷口、车灯和人群进行追查", "dialogue_role": None},
            {"duration": 4, "shot_type": "detail", "camera_angle": "extreme-close-up", "camera_movement": "zoom_in", "emotion": "surprised", "lighting": "rim", "color_grading": "noir", "visual_focus": "监控截图、门禁卡、定位点或血迹线索", "dialogue_role": None},
            {"duration": 4, "shot_type": "dialogue", "camera_angle": "over-shoulder", "camera_movement": "pan_right", "emotion": "tense", "lighting": "dramatic", "color_grading": "cool", "visual_focus": "主角和搭档压低声音确认线索", "dialogue_role": "角色"},
            {"duration": 5, "shot_type": "transition", "camera_angle": "wide", "camera_movement": "zoom_out", "emotion": "tense", "lighting": "back", "color_grading": "noir", "visual_focus": "镜头拉远显示追查者也被跟踪", "dialogue_role": "旁白"},
        ],
    },
]


def list_templates() -> List[Dict[str, Any]]:
    return copy.deepcopy(STORYBOARD_TEMPLATES)


def get_template(
    template_id: Optional[str],
    templates: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    if not template_id:
        return None
    template_pool = templates or STORYBOARD_TEMPLATES
    return next((template for template in template_pool if template["id"] == template_id), None)


def _get_asset_value(asset: Any, key: str, default: Any = None) -> Any:
    if isinstance(asset, dict):
        return asset.get(key, default)
    return getattr(asset, key, default)


def _unique_texts(values: List[Any]) -> List[str]:
    result: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _normalize_shot_pattern(
    base_pattern: Optional[Dict[str, Any]],
    override_pattern: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    pattern = {
        **DEFAULT_SHOT_PATTERN,
        **(base_pattern or {}),
        **(override_pattern or {}),
    }
    try:
        pattern["duration"] = max(4, min(10, int(pattern.get("duration") or 4)))
    except (TypeError, ValueError):
        pattern["duration"] = 4
    return pattern


def normalize_template_shots(
    base_shots: List[Dict[str, Any]],
    override_shots: Optional[List[Dict[str, Any]]] = None,
    shot_count: Optional[int] = None,
) -> List[Dict[str, Any]]:
    base_patterns = base_shots or [DEFAULT_SHOT_PATTERN]
    override_patterns = [shot for shot in (override_shots or []) if isinstance(shot, dict)]
    target_count = shot_count or len(override_patterns) or len(base_patterns)
    target_count = max(1, min(50, int(target_count or 1)))
    return [
        _normalize_shot_pattern(
            base_patterns[index % len(base_patterns)],
            override_patterns[index] if index < len(override_patterns) else None,
        )
        for index in range(target_count)
    ]


def _system_template_id_from_asset(asset: Any) -> Optional[str]:
    shot_template = _get_asset_value(asset, "shot_template") or {}
    if not isinstance(shot_template, dict):
        return None
    system_template_id = str(shot_template.get("system_template_id") or "").strip()
    if system_template_id:
        return system_template_id
    style_tags = _get_asset_value(asset, "style_tags") or []
    for tag in style_tags:
        text = str(tag or "").strip()
        if text.startswith("system_template:"):
            return text.split(":", 1)[1].strip() or None
    return None


def merge_template_overrides(
    base_templates: List[Dict[str, Any]],
    override_assets: List[Any],
) -> List[Dict[str, Any]]:
    """Apply user-owned Asset overrides while preserving stable system IDs."""
    overrides_by_system_id: Dict[str, Any] = {}
    for asset in override_assets:
        system_template_id = _system_template_id_from_asset(asset)
        if system_template_id:
            overrides_by_system_id.setdefault(system_template_id, asset)

    merged_templates: List[Dict[str, Any]] = []
    for base_template in base_templates:
        template = copy.deepcopy(base_template)
        override = overrides_by_system_id.get(template["id"])
        if not override:
            template.setdefault("is_system", True)
            template.setdefault("is_overridden", False)
            template.setdefault("shot_template", {"shot_count": len(template["shots"]), "shots": template["shots"]})
            merged_templates.append(template)
            continue

        shot_template = _get_asset_value(override, "shot_template") or {}
        if not isinstance(shot_template, dict):
            shot_template = {}
        tags = _unique_texts(_get_asset_value(override, "tags") or template.get("genre_tags") or [])
        keywords = _unique_texts(
            (shot_template.get("keywords") or [])
            + tags
            + (template.get("keywords") or [])
        )
        shot_count = shot_template.get("shot_count") or len(shot_template.get("shots") or []) or len(template["shots"])
        template["name"] = _get_asset_value(override, "name") or template["name"]
        template["description"] = _get_asset_value(override, "description") or template["description"]
        template["genre_tags"] = tags or template["genre_tags"]
        template["keywords"] = keywords or template["keywords"]
        template["prompt_template"] = _get_asset_value(override, "prompt_template")
        template["shots"] = normalize_template_shots(
            template["shots"],
            shot_template.get("shots") if isinstance(shot_template.get("shots"), list) else None,
            shot_count=shot_count,
        )
        template["shot_template"] = {
            **shot_template,
            "system_template_id": template["id"],
            "shot_count": len(template["shots"]),
            "shots": template["shots"],
        }
        template["is_system"] = True
        template["is_overridden"] = True
        template["override_asset_id"] = str(_get_asset_value(override, "id"))
        merged_templates.append(template)

    return merged_templates


def match_storyboard_template(
    *,
    title: str = "",
    genre: str = "",
    content: str = "",
    template_id: Optional[str] = None,
    templates: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    template_pool = templates or STORYBOARD_TEMPLATES
    selected = get_template(template_id, template_pool)
    if selected:
        return {"template": selected, "score": 999, "reason": "用户指定模板"}

    haystack = f"{title}\n{genre}\n{content}".lower()
    best: Optional[Dict[str, Any]] = None
    best_score = -1
    reasons: List[str] = []

    for template in template_pool:
        score = 0
        matched_reasons: List[str] = []
        for tag in template["genre_tags"]:
            if tag and tag.lower() in haystack:
                score += 5
                matched_reasons.append(f"题材匹配：{tag}")
        for keyword in template["keywords"]:
            count = haystack.count(keyword.lower())
            if count:
                score += min(count, 3) * 2
                matched_reasons.append(f"关键词：{keyword}")
        if score > best_score:
            best = template
            best_score = score
            reasons = matched_reasons

    if best is None:
        best = template_pool[0]
        best_score = 0
    return {
        "template": best,
        "score": best_score,
        "reason": "；".join(reasons[:4]) if reasons else "未命中强特征，使用通用动漫分镜结构",
    }


def extract_story_beats(content: str, desired_count: int) -> List[str]:
    beats = extract_raw_story_beats(content)
    if not beats:
        beats = ["故事开场", "人物行动", "情节推进", "结果确认"]
    while len(beats) < desired_count:
        beats.append(beats[-1])
    return beats[:desired_count]


def _clean_story_beat(value: str) -> str:
    return (value or "").strip().strip(" ，；;:：")


def _split_story_sentences(text: str) -> List[str]:
    """Split Chinese prose without breaking punctuation inside paired quotes."""
    parts: List[str] = []
    buffer: List[str] = []
    quote_stack: List[str] = []
    open_quotes = {"“": "”", "「": "」", "『": "』"}
    close_quotes = {value: key for key, value in open_quotes.items()}
    sentence_end = set("。！？；!?;\n")

    for index, char in enumerate(text):
        if char in open_quotes:
            quote_stack.append(char)
        buffer.append(char)

        if char in close_quotes:
            if quote_stack and quote_stack[-1] == close_quotes[char]:
                quote_stack.pop()
            previous = next((item for item in reversed(buffer[:-1]) if item.strip()), "")
            if not quote_stack and previous in sentence_end:
                part = _clean_story_beat("".join(buffer))
                if part:
                    parts.append(part)
                buffer = []
            continue

        if char in sentence_end and not quote_stack:
            next_char = text[index + 1] if index + 1 < len(text) else ""
            if next_char in close_quotes:
                continue
            part = _clean_story_beat("".join(buffer))
            if part:
                parts.append(part)
            buffer = []

    tail = _clean_story_beat("".join(buffer))
    if tail:
        parts.append(tail)
    return parts


def extract_raw_story_beats(content: str) -> List[str]:
    cleaned = re.sub(r"\s+", " ", content or "").strip()
    if not cleaned:
        return []
    parts = _split_story_sentences(cleaned)
    if not parts:
        parts = [cleaned[:80]]
    beats: List[str] = []
    for part in parts:
        if len(part) > 90:
            sub_parts = [part[i:i + 70] for i in range(0, len(part), 70)]
            beats.extend(sub_parts)
        else:
            beats.append(part)
    return beats


def plan_storyboard_shot_count(
    *,
    template: Dict[str, Any],
    source_content: str,
    requested_shot_count: Optional[int] = None,
) -> Dict[str, Any]:
    template_count = max(1, len(template.get("shots") or []))
    if requested_shot_count is not None:
        shot_count = max(1, min(50, int(requested_shot_count)))
        return {
            "source": "requested",
            "shot_count": shot_count,
            "requested_shot_count": shot_count,
            "story_beat_count": len(extract_raw_story_beats(source_content)),
            "template_shot_count": template_count,
            "reason": "使用用户指定镜头数量",
        }

    beats = extract_raw_story_beats(source_content)
    beat_count = len(beats)
    text_length = len(re.sub(r"\s+", "", source_content or ""))
    action_keyword_count = len(re.findall(r"战|追|逃|冲|爆|打|杀|剑|枪|跳|跑|危机|逼近|倒计时", source_content or ""))
    dialogue_hint_count = len(re.findall(r"[：:「“\"]", source_content or ""))

    if beat_count <= 1:
        shot_count = 2
    elif beat_count <= 2:
        shot_count = 3
    elif beat_count <= 4:
        shot_count = 3 if text_length <= 260 else beat_count
    else:
        shot_count = min(8, beat_count)

    if text_length >= 600:
        shot_count = max(shot_count, min(8, round(text_length / 180)))
    if action_keyword_count >= 4 or dialogue_hint_count >= 4:
        shot_count = max(shot_count, min(8, beat_count + 1 if beat_count else template_count))

    if beat_count >= 2:
        shot_count = min(shot_count, beat_count)

    shot_count = max(2, min(8, shot_count))
    return {
        "source": "auto",
        "shot_count": shot_count,
        "requested_shot_count": None,
        "story_beat_count": beat_count,
        "template_shot_count": template_count,
        "text_length": text_length,
        "action_keyword_count": action_keyword_count,
        "dialogue_hint_count": dialogue_hint_count,
        "reason": "根据情节点数量、文本长度、动作/对白密度自动规划镜头数量",
    }


def _story_context_items(story_context: Optional[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    items = (story_context or {}).get(key) or []
    return [item for item in items if isinstance(item, dict)]


def _story_context_names(story_context: Optional[Dict[str, Any]], key: str, limit: int = 4) -> List[str]:
    names: List[str] = []
    for item in _story_context_items(story_context, key):
        name = str(item.get("name") or item.get("title") or "").strip()
        if name and name not in names:
            names.append(name)
        if len(names) >= limit:
            break
    return names


def _is_trusted_character_name(name: str) -> bool:
    text = re.sub(r"\s+", "", name or "")
    if not re.fullmatch(r"[\u4e00-\u9fff]{2,6}", text):
        return False
    if text in {"角色A", "角色B", "角色C", "某人", "主角", "她", "他", "他们", "她们", "两人"}:
        return False
    if any(marker in text for marker in ("说", "回答", "低声", "不是", "而是", "只在", "因果", "字幕", "对白")):
        return False
    if text.endswith(("港", "码头", "机房", "灯塔", "星锚室", "罗盘", "围巾", "工具包", "铜钥匙", "铜铃")):
        return False
    return True


def _trusted_character_names(story_context: Optional[Dict[str, Any]], limit: int = 4) -> List[str]:
    return [name for name in _story_context_names(story_context, "characters", limit=limit * 2) if _is_trusted_character_name(name)][:limit]


def _mentioned_character_names(beat: str, characters: List[str]) -> List[str]:
    return [name for name in characters if name and name in (beat or "")]


def _extract_direct_dialogue(
    beat: str,
    characters: List[str],
    *,
    speaker_hint: Optional[str] = None,
) -> Optional[tuple[str, str]]:
    text = (beat or "").strip()
    if not text or not characters:
        return None
    for speaker in characters:
        for pattern in (
            re.compile(rf"{re.escape(speaker)}(?:低声说|低声道|回答|说道|说|问|喊)[：:]?\s*[“\"']?([^”\"'。！？]+)"),
            re.compile(rf"{re.escape(speaker)}[^。！？；“”\"']{{0,16}}(?:低声说|低声道|回答|说道|说|问|喊)[：:]?\s*[“\"']?([^”\"'。！？]+)"),
            re.compile(rf"{re.escape(speaker)}[：:]\s*[“\"']?([^”\"'。！？]+)"),
        ):
            match = pattern.search(text)
            if match:
                line = _short_clause(match.group(1), 44)
                if line:
                    return speaker, line
    if speaker_hint and speaker_hint in characters:
        pronoun_match = re.search(r"(?:[他她它]|TA)?(?:低声说|低声道|回答|说道|说|问|喊)[：:]?\s*[“\"']([^”\"'。！？]+)", text)
        if pronoun_match:
            line = _short_clause(pronoun_match.group(1), 44)
            if line:
                return speaker_hint, line
    return None


def _first_context_name(story_context: Optional[Dict[str, Any]], key: str) -> Optional[str]:
    names = _story_context_names(story_context, key, limit=1)
    return names[0] if names else None


def _short_clause(value: str, limit: int = 42) -> str:
    text = re.sub(r"\s+", "", value or "").strip(" ，。！？；:：")
    if len(text) <= limit:
        return text
    return text[:limit].rstrip("，、；")


def _with_sentence_punctuation(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if text.endswith(("。", "！", "？", "；", "!", "?", "。”", "！”", "？”", "；”")):
        return text
    return f"{text}。"


def _sanitize_narration_clause(value: str) -> str:
    text = (value or "").strip()
    text = re.sub(r"^[他她它](?:低声说|低声道|说道|说|问|喊)[：:][“\"']?", "", text)
    return text.strip(" ，。！？；:：") or (value or "").strip()


def _select_template_dialogue_speaker(
    *,
    beat: str,
    characters: List[str],
    shot_index: int,
    speaker_hint: Optional[str],
) -> Optional[str]:
    mentioned = _mentioned_character_names(beat, characters)
    for candidate in [
        mentioned[-1] if mentioned else None,
        speaker_hint if speaker_hint in characters else None,
        characters[shot_index % len(characters)] if characters else None,
    ]:
        if candidate:
            return candidate
    return None


def _build_character_fallback_line(
    *,
    beat_clause: str,
    speaker: str,
    scene: Optional[str],
    prop: Optional[str],
    event: Optional[str],
) -> str:
    clean = _sanitize_narration_clause(beat_clause)
    clean = clean.replace(speaker, "").strip(" ，。！？；:：") or clean
    if prop and prop in clean:
        return _with_sentence_punctuation(f"{prop}的异常必须马上确认")
    if event and event in clean:
        return _with_sentence_punctuation(f"这件事不能再拖了")
    if scene and scene in clean:
        return _with_sentence_punctuation(f"这里不对劲，我们得立刻行动")
    if any(marker in clean for marker in ("危险", "异常", "倒计时", "追踪", "追杀", "失控")):
        return _with_sentence_punctuation("不对，这里一定有问题")
    return _with_sentence_punctuation("我必须弄清楚真相")


def _build_template_dialogue(
    *,
    dialogue_role: Optional[str],
    beat: str,
    shot_index: int,
    story_context: Optional[Dict[str, Any]],
    speaker_hint: Optional[str] = None,
) -> Optional[str]:
    characters = _trusted_character_names(story_context)
    direct_dialogue = _extract_direct_dialogue(beat, characters, speaker_hint=speaker_hint)
    if direct_dialogue:
        speaker, line = direct_dialogue
        return f"{speaker}：{line}。"

    if not dialogue_role:
        return None

    scene = _first_context_name(story_context, "scenes")
    prop = _first_context_name(story_context, "props")
    event = _first_context_name(story_context, "events")
    beat_clause = _short_clause(beat)

    if dialogue_role == "旁白":
        return f"（旁白）{_with_sentence_punctuation(_sanitize_narration_clause(beat_clause))}"

    if dialogue_role == "角色":
        speaker = _select_template_dialogue_speaker(
            beat=beat,
            characters=characters,
            shot_index=shot_index,
            speaker_hint=speaker_hint,
        )
        if not speaker:
            return f"（旁白）{_with_sentence_punctuation(_sanitize_narration_clause(beat_clause))}"
        line = _build_character_fallback_line(
            beat_clause=beat_clause,
            speaker=speaker,
            scene=scene,
            prop=prop,
            event=event,
        )
        return f"{speaker}：{line}"

    return None


def _extract_template_dialogue_speaker(dialogue: Optional[str]) -> Optional[str]:
    text = (dialogue or "").strip()
    if not text:
        return None
    narrator_match = re.match(r"^（\s*([^）]{1,12})\s*）", text)
    if narrator_match:
        return narrator_match.group(1).strip()
    match = re.match(r"^\s*([^：:（）()，。！？\n]{1,24})\s*[：:]", text)
    return match.group(1).strip() if match else None


def build_template_shots(
    *,
    template: Dict[str, Any],
    source_title: str,
    source_content: str,
    shot_count: Optional[int] = None,
    story_context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    patterns = template["shots"]
    target_count = plan_storyboard_shot_count(
        template=template,
        source_content=source_content,
        requested_shot_count=shot_count,
    )["shot_count"]
    beats = extract_story_beats(source_content, target_count)
    compact_text_length = len(re.sub(r"\s+", "", source_content or ""))
    duration_cap = 4 if target_count <= 3 and compact_text_length <= 260 else 10
    shots: List[Dict[str, Any]] = []
    characters = _trusted_character_names(story_context)
    last_mentioned_character: Optional[str] = None

    for index in range(target_count):
        pattern = patterns[index % len(patterns)]
        beat = beats[index]
        visual_focus = pattern["visual_focus"]
        dialogue_role = pattern.get("dialogue_role")
        mentioned_characters = _mentioned_character_names(beat, characters)
        dialogue = _build_template_dialogue(
            dialogue_role=dialogue_role,
            beat=beat,
            shot_index=index,
            story_context=story_context,
            speaker_hint=last_mentioned_character,
        )
        if mentioned_characters:
            last_mentioned_character = mentioned_characters[-1]
        else:
            extracted_speaker = _extract_template_dialogue_speaker(dialogue)
            if extracted_speaker and extracted_speaker != "旁白":
                last_mentioned_character = extracted_speaker

        shots.append(
            {
                "shot_number": index + 1,
                "duration": max(4, min(duration_cap, int(pattern["duration"]))),
                "shot_type": pattern["shot_type"],
                "prompt": f"{source_title}，{beat[:50]}，{visual_focus}",
                "dialogue": dialogue,
                "visual_description": (
                    f"{visual_focus}。画面围绕“{beat[:90]}”展开，保持人物服装、场景空间、"
                    "道具状态和事件顺序连续，动漫电影质感。"
                ),
                "camera_angle": pattern["camera_angle"],
                "camera_movement": pattern["camera_movement"],
                "movement_speed": 1.0,
                "emotion": pattern["emotion"],
                "emotion_intensity": 0.7 if pattern["emotion"] in {"tense", "angry", "excited", "sad"} else 0.5,
                "lighting": pattern["lighting"],
                "color_grading": pattern["color_grading"],
                "sound_effect": "环境音、脚步声、衣料摩擦" if pattern["shot_type"] != "action" else "急促脚步、撞击声、风声",
                "music_mood": "紧张推进" if pattern["emotion"] == "tense" else "情绪铺垫",
                "ambient_sound": "与当前场景匹配的环境底噪",
                "keyframes": [
                    {"time": 0.0, "prompt": f"镜头开始：{visual_focus}"},
                    {"time": 0.5, "prompt": f"情节推进：{beat[:50]}"},
                    {"time": 1.0, "prompt": "镜头结束，保留下一镜头衔接空间"},
                ],
                "extra_data": {
                    "template_id": template["id"],
                    "template_name": template["name"],
                    "source_beat": beat,
                    "dialogue_speaker": _extract_template_dialogue_speaker(dialogue),
                    "dialogue_source": "template_story_beat",
                    "dialogue_intent": dialogue_role,
                    "review_status": "pending_review",
                    "automation_level": "template_draft",
                },
            }
        )
    return shots
