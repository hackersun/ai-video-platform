"""
Default anime production starter library.

The records are user-scoped so they can be edited, archived, or rebound to a
novel without mutating shared system rows.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, StoryEntity

STARTER_SOURCE = "starter"


DEFAULT_ANIME_ENTITIES: list[dict[str, Any]] = [
    {
        "key": "character-hotblood-lead",
        "entity_type": "character",
        "name": "热血少年主角",
        "description": "适合短剧开场的行动型主角，目标明确，情绪外放，容易制造钩子。",
        "aliases": ["少年主角", "行动派主角"],
        "attributes": {
            "visual_dna": {"age": "16-22", "hair": "黑色短发", "costume": "校服或轻便外套", "silhouette": "清瘦但有爆发力"},
            "personality": ["冲动", "守护欲强", "不服输"],
            "voice_profile": {"tone": "少年感", "pace": "偏快", "emotion": "坚定"},
            "asset_pack": {"required": ["front", "side", "full_body", "neutral", "angry", "determined"]},
        },
    },
    {
        "key": "character-calm-female-lead",
        "entity_type": "character",
        "name": "冷静行动女主",
        "description": "适合悬疑、都市异能或玄幻题材的理性女主，负责观察、分析和推进关键线索。",
        "aliases": ["女主", "冷静搭档"],
        "attributes": {
            "visual_dna": {"hair": "长发或利落短发", "eyes": "冷色高光", "costume": "制服、风衣或轻战斗服"},
            "personality": ["冷静", "敏锐", "嘴硬心软"],
            "voice_profile": {"tone": "清冷", "pace": "稳定", "emotion": "克制"},
            "relationships": [{"target": "热血少年主角", "type": "搭档", "status": "互相试探"}],
        },
    },
    {
        "key": "character-mysterious-mentor",
        "entity_type": "character",
        "name": "神秘导师",
        "description": "提供世界观、规则和关键任务的引导者，适合在第一集后半段埋下更大悬念。",
        "aliases": ["导师", "引路人"],
        "attributes": {
            "visual_dna": {"costume": "长外套或古风长袍", "prop": "旧书、烟斗或通讯终端", "expression": "若有所知"},
            "personality": ["克制", "隐藏信息", "测试主角"],
            "voice_profile": {"tone": "低沉", "pace": "慢", "emotion": "压迫感低"},
        },
    },
    {
        "key": "character-pressure-villain",
        "entity_type": "character",
        "name": "压迫型反派",
        "description": "短视频强冲突角色，可用于追杀、威胁、揭露秘密或制造结尾反转。",
        "aliases": ["反派", "追击者"],
        "attributes": {
            "visual_dna": {"silhouette": "高挑或厚重", "color": "暗红/黑金", "signature": "面具、手套或发光纹路"},
            "personality": ["冷酷", "掌控欲", "压迫感强"],
            "voice_profile": {"tone": "低压", "pace": "慢", "emotion": "威胁"},
        },
    },
    {
        "key": "scene-city-night-alley",
        "entity_type": "scene",
        "name": "城市夜巷",
        "description": "适合开场追逐、秘密交易、初次能力觉醒的低成本通用场景。",
        "attributes": {
            "scene_tags": ["室外", "夜晚", "追逐", "悬疑"],
            "scene_dna": {"lighting": "霓虹反光与冷蓝路灯", "weather": "雨后潮湿", "layout": "狭窄巷道、招牌、积水"},
        },
    },
    {
        "key": "scene-school-rooftop",
        "entity_type": "scene",
        "name": "学校天台",
        "description": "适合青春、校园异能、告白、对峙和世界观揭示。",
        "attributes": {
            "scene_tags": ["室外", "日常", "对话", "校园"],
            "scene_dna": {"lighting": "黄昏逆光", "layout": "铁丝网、天台门、水箱", "mood": "安静但有风"},
        },
    },
    {
        "key": "scene-fantasy-palace",
        "entity_type": "scene",
        "name": "玄幻大殿",
        "description": "适合宗门审判、主角觉醒、反派压迫和高能转场。",
        "attributes": {
            "scene_tags": ["室内", "玄幻", "仪式", "压迫"],
            "scene_dna": {"lighting": "金色烛火与高处天光", "layout": "高台、石柱、符文地面", "scale": "宏大"},
        },
    },
    {
        "key": "scene-cyber-lab",
        "entity_type": "scene",
        "name": "赛博实验室",
        "description": "适合科幻、都市异能、失控实验和关键道具解析。",
        "attributes": {
            "scene_tags": ["室内", "科幻", "实验", "危机"],
            "scene_dna": {"lighting": "青绿色屏幕光", "layout": "培养舱、全息屏、线缆", "mood": "冷硬"},
        },
    },
    {
        "key": "prop-destiny-pendant",
        "entity_type": "prop",
        "name": "命运吊坠",
        "description": "可承载身份、封印、时间回溯或能力觉醒的关键道具。",
        "attributes": {
            "prop_dna": {"material": "青铜或银色金属", "shape": "几何吊坠", "marking": "裂纹、符文或星纹"},
            "state_flow": ["完好", "出现裂纹", "发光", "解锁隐藏信息"],
        },
    },
    {
        "key": "prop-energy-core",
        "entity_type": "prop",
        "name": "能量核心",
        "description": "适合赛博、机甲、魔法装置和短视频结尾高能反转。",
        "attributes": {
            "prop_dna": {"material": "透明晶体与金属框架", "color": "蓝紫能量光", "motion": "内部流动光带"},
            "state_flow": ["稳定", "过载", "破裂", "释放能量"],
        },
    },
    {
        "key": "event-opening-crisis",
        "entity_type": "event",
        "name": "开场危机",
        "description": "短剧式第一镜头常用事件：3 秒内抛出危险、倒计时或强问题。",
        "attributes": {
            "sequence": 1,
            "beat_type": "hook",
            "participants": ["热血少年主角", "压迫型反派"],
            "purpose": "快速建立冲突和观看动机",
        },
    },
    {
        "key": "event-clue-discovery",
        "entity_type": "event",
        "name": "线索发现",
        "description": "推动剧情从日常进入主线的通用事件，适合承接道具、场景和人物关系。",
        "attributes": {
            "sequence": 2,
            "beat_type": "turning_point",
            "participants": ["热血少年主角", "冷静行动女主"],
            "prop_state_changes": [{"prop": "命运吊坠", "from": "普通饰品", "to": "显示隐藏纹路"}],
        },
    },
    {
        "key": "event-ending-reversal",
        "entity_type": "event",
        "name": "结尾反转",
        "description": "短视频结尾常用悬念：身份揭露、道具失控或下一集危机。",
        "attributes": {
            "sequence": 99,
            "beat_type": "cliffhanger",
            "purpose": "制造下集承接",
        },
    },
    {
        "key": "character-xianxia-sword-cultivator",
        "entity_type": "character",
        "name": "少年剑修",
        "description": "修仙/仙侠题材通用主角，适合御剑、突破、宗门试炼和秘境探索。",
        "aliases": ["剑修主角", "外门弟子"],
        "attributes": {
            "visual_dna": {"age": "16-24", "hair": "黑发束冠", "costume": "青白弟子服", "signature": "背负长剑与玉牌"},
            "personality": ["坚韧", "重情义", "不甘平庸"],
            "voice_profile": {"tone": "少年感", "pace": "稳定", "emotion": "克制后爆发"},
            "asset_pack": {"required": ["front", "side", "full_body", "sword_pose", "breakthrough_expression"]},
        },
    },
    {
        "key": "character-xianxia-sect-elder",
        "entity_type": "character",
        "name": "宗门长老",
        "description": "宗门审判、传功、压迫或试炼发布的权威角色。",
        "aliases": ["长老", "戒律长老"],
        "attributes": {
            "visual_dna": {"costume": "深色长袍与宗门纹样", "prop": "拂尘、戒尺或身份玉牌", "expression": "威严"},
            "personality": ["威严", "守规矩", "隐藏立场"],
            "voice_profile": {"tone": "低沉", "pace": "慢", "emotion": "压迫"},
        },
    },
    {
        "key": "character-wuxia-jianghu-swordsman",
        "entity_type": "character",
        "name": "江湖剑客",
        "description": "武侠题材通用侠客角色，适合客栈对峙、擂台比武和夜探门派。",
        "aliases": ["侠客", "剑客"],
        "attributes": {
            "visual_dna": {"costume": "深色劲装或斗笠披风", "prop": "长剑、酒葫芦", "silhouette": "利落挺拔"},
            "personality": ["重义气", "寡言", "恩怨分明"],
            "voice_profile": {"tone": "沉稳", "pace": "短句", "emotion": "含蓄"},
        },
    },
    {
        "key": "character-xuanhuan-bloodline-heir",
        "entity_type": "character",
        "name": "血脉继承者",
        "description": "玄幻题材觉醒型角色，可用于血脉、神器、异兽和古遗迹线。",
        "aliases": ["继承者", "血脉主角"],
        "attributes": {
            "visual_dna": {"marking": "瞳孔或手背族纹", "costume": "皮甲与披肩", "aura": "金红或蓝紫能量纹"},
            "personality": ["谨慎", "背负秘密", "爆发力强"],
            "voice_profile": {"tone": "压抑", "pace": "由慢到快", "emotion": "觉醒时高燃"},
        },
    },
    {
        "key": "character-urban-power-user",
        "entity_type": "character",
        "name": "都市异能者",
        "description": "现代都市/校园/职场中突然觉醒能力的通用角色。",
        "aliases": ["异能主角", "觉醒者"],
        "attributes": {
            "visual_dna": {"costume": "连帽外套、校服或职场外套", "prop": "手机、耳机或门禁卡", "aura": "微弱电弧或数据光"},
            "personality": ["警觉", "不愿暴露", "快速适应"],
            "voice_profile": {"tone": "现代口语", "pace": "偏快", "emotion": "紧张"},
        },
    },
    {
        "key": "scene-xianxia-sect-gate",
        "entity_type": "scene",
        "name": "仙门山门",
        "description": "修仙宗门入口，适合入门试炼、宗门审判前置和御剑归来。",
        "attributes": {
            "scene_tags": ["室外", "修仙", "宗门", "山门", "云海"],
            "scene_dna": {"lighting": "云海天光", "layout": "巨大牌坊、长阶、浮云、远山", "mood": "庄严"},
        },
    },
    {
        "key": "scene-xianxia-cave-abode",
        "entity_type": "scene",
        "name": "修炼洞府",
        "description": "适合闭关、突破、雷劫前兆和法宝觉醒。",
        "attributes": {
            "scene_tags": ["室内", "修仙", "修炼", "突破"],
            "scene_dna": {"lighting": "灵石微光", "layout": "蒲团、阵法纹、石壁、灵草", "mood": "静谧转高压"},
        },
    },
    {
        "key": "scene-wuxia-inn",
        "entity_type": "scene",
        "name": "江湖客栈",
        "description": "武侠剧情通用冲突场景，适合初遇、交易、对峙和打斗。",
        "attributes": {
            "scene_tags": ["室内", "武侠", "江湖", "对话", "打斗"],
            "scene_dna": {"lighting": "暖色油灯", "layout": "木桌、二楼栏杆、酒旗、门口风沙", "mood": "热闹下藏杀机"},
        },
    },
    {
        "key": "scene-wuxia-bamboo-forest",
        "entity_type": "scene",
        "name": "竹林山道",
        "description": "武侠轻功、埋伏、刀剑对决和离别常用场景。",
        "attributes": {
            "scene_tags": ["室外", "武侠", "竹林", "埋伏", "对决"],
            "scene_dna": {"lighting": "斑驳日光或月光", "layout": "竹影、碎石路、雾气", "mood": "清冷肃杀"},
        },
    },
    {
        "key": "scene-xuanhuan-secret-realm",
        "entity_type": "scene",
        "name": "古遗迹秘境",
        "description": "玄幻冒险通用秘境，适合神器现世、异兽遭遇和血脉觉醒。",
        "attributes": {
            "scene_tags": ["室外", "玄幻", "秘境", "遗迹", "探索"],
            "scene_dna": {"lighting": "金蓝能量光", "layout": "浮空石阶、古碑、祭坛、断裂石柱", "scale": "宏大"},
        },
    },
    {
        "key": "scene-urban-subway-platform",
        "entity_type": "scene",
        "name": "城市地铁站台",
        "description": "都市异能觉醒、追逐、监控线索和人群危机常用现代场景。",
        "attributes": {
            "scene_tags": ["室内", "都市", "现代", "追逐", "人群"],
            "scene_dna": {"lighting": "冷白灯与广告屏", "layout": "站台、闸机、监控、电子屏", "mood": "日常突变"},
        },
    },
    {
        "key": "scene-urban-hidden-lab",
        "entity_type": "scene",
        "name": "隐藏异能实验室",
        "description": "都市异能和科幻线常用组织据点，适合能力检测和阴谋揭示。",
        "attributes": {
            "scene_tags": ["室内", "都市异能", "实验室", "组织", "危机"],
            "scene_dna": {"lighting": "青绿色屏幕光", "layout": "隔离舱、线缆、监控墙、实验台", "mood": "冷硬压迫"},
        },
    },
    {
        "key": "prop-xianxia-spirit-sword",
        "entity_type": "prop",
        "name": "本命灵剑",
        "description": "修仙/武侠都可复用的主武器，适合御剑、比武和突破护体。",
        "attributes": {
            "prop_dna": {"material": "青钢或玉质剑身", "marking": "细密符文", "aura": "青白剑气"},
            "state_flow": ["沉寂", "轻鸣", "出鞘", "剑气爆发"],
        },
    },
    {
        "key": "prop-xianxia-jade-token",
        "entity_type": "prop",
        "name": "宗门玉牌",
        "description": "用于身份、任务、审判证据和宗门结界通行。",
        "attributes": {
            "prop_dna": {"material": "白玉", "shape": "长方玉牌", "marking": "宗门徽纹与灵光编号"},
            "state_flow": ["普通身份牌", "发光示警", "裂纹", "暴露隐藏身份"],
        },
    },
    {
        "key": "prop-wuxia-secret-manual",
        "entity_type": "prop",
        "name": "残页秘籍",
        "description": "武侠门派恩怨、夜探和擂台反转常用关键道具。",
        "attributes": {
            "prop_dna": {"material": "泛黄纸页", "marking": "残缺招式图与朱砂批注", "wear": "边角破损"},
            "state_flow": ["残缺", "拼合", "发现夹层", "引发追杀"],
        },
    },
    {
        "key": "prop-xuanhuan-beast-core",
        "entity_type": "prop",
        "name": "异兽灵核",
        "description": "玄幻秘境和异兽遭遇中的能量道具，可触发觉醒或炼化。",
        "attributes": {
            "prop_dna": {"material": "半透明晶核", "color": "金红/蓝紫能量涡旋", "motion": "内部光带旋转"},
            "state_flow": ["封存", "共鸣", "过载", "融入血脉"],
        },
    },
    {
        "key": "prop-urban-access-card",
        "entity_type": "prop",
        "name": "组织门禁卡",
        "description": "都市异能追查线常用线索，可串联实验室、隐藏组织和监控。",
        "attributes": {
            "prop_dna": {"material": "黑色磨砂卡片", "marking": "银色编号与微型芯片", "glow": "刷卡时蓝光"},
            "state_flow": ["遗失", "被捡到", "破解", "暴露入口"],
        },
    },
    {
        "key": "event-xianxia-breakthrough",
        "entity_type": "event",
        "name": "境界突破",
        "description": "修仙题材关键爽点事件，伴随灵气汇聚、雷劫、法宝护体和境界变化。",
        "attributes": {
            "sequence": 10,
            "beat_type": "power_up",
            "participants": ["少年剑修"],
            "prop_state_changes": [{"prop": "本命灵剑", "from": "沉寂", "to": "剑气爆发"}],
        },
    },
    {
        "key": "event-wuxia-duel",
        "entity_type": "event",
        "name": "江湖比武",
        "description": "武侠题材推动恩怨、门派声望和秘籍线索的核心事件。",
        "attributes": {
            "sequence": 20,
            "beat_type": "duel",
            "participants": ["江湖剑客"],
            "purpose": "用胜负和侠义选择推动人物关系",
        },
    },
    {
        "key": "event-xuanhuan-secret-realm-open",
        "entity_type": "event",
        "name": "秘境开启",
        "description": "玄幻冒险入口事件，用于引出神器、异兽、遗迹规则和队伍冲突。",
        "attributes": {
            "sequence": 30,
            "beat_type": "adventure_entry",
            "location": "古遗迹秘境",
            "prop_state_changes": [{"prop": "异兽灵核", "from": "封存", "to": "共鸣"}],
        },
    },
    {
        "key": "event-urban-power-awakening",
        "entity_type": "event",
        "name": "都市异能觉醒",
        "description": "现代日常被异常打破，主角能力暴露并被隐藏组织锁定。",
        "attributes": {
            "sequence": 40,
            "beat_type": "awakening",
            "participants": ["都市异能者"],
            "location": "城市地铁站台",
            "purpose": "把现代生活转入超自然主线",
        },
    },
]


DEFAULT_ANIME_ASSETS: list[dict[str, Any]] = [
    {
        "key": "asset-character-consistency-prompt",
        "category": "prompt",
        "name": "角色一致性提示词",
        "asset_type": "text",
        "description": "用于角色图、分镜和视频生成，强调脸型、发型、服装、身形和标志物保持一致。",
        "tags": ["系统预置", "角色一致性", "提示词"],
        "style_tags": ["anime", "production"],
        "prompt_template": "保持{{character}}的脸型、发型、瞳色、体型、服装、标志物完全一致；如剧情未说明，不改变服装和道具状态。",
        "variables": [{"name": "character", "type": "character_ref"}],
    },
    {
        "key": "asset-short-video-hook-prompt",
        "category": "prompt",
        "name": "短视频开场钩子提示词",
        "asset_type": "text",
        "description": "适合 9:16 动漫短剧开头 3 秒，快速呈现危机、问题或反转。",
        "tags": ["系统预置", "短剧", "开场"],
        "style_tags": ["anime", "vertical-video"],
        "prompt_template": "前 3 秒必须出现明确危机或强问题：{{hook}}；画面优先使用近景或冲击性构图，避免铺垫过长。",
        "variables": [{"name": "hook", "type": "text"}],
    },
    {
        "key": "asset-city-night-reference",
        "category": "scene",
        "name": "城市夜巷场景参考",
        "asset_type": "text",
        "description": "霓虹、雨后地面、窄巷、冷蓝光，适合追逐和悬疑开场。",
        "tags": ["系统预置", "城市", "夜景", "追逐"],
        "style_tags": ["anime", "neon", "cool-light"],
        "prompt_template": "城市夜巷，雨后湿润地面反射霓虹，冷蓝路灯，狭窄透视，动漫电影感。",
    },
    {
        "key": "asset-school-rooftop-reference",
        "category": "scene",
        "name": "学校天台场景参考",
        "asset_type": "text",
        "description": "黄昏逆光、铁丝网、微风，适合青春对话和关键告白。",
        "tags": ["系统预置", "校园", "黄昏", "对话"],
        "style_tags": ["anime", "warm-light"],
        "prompt_template": "学校天台，黄昏逆光，铁丝网边缘，微风吹动衣摆，青春动漫氛围。",
    },
    {
        "key": "asset-fantasy-palace-reference",
        "category": "scene",
        "name": "玄幻大殿场景参考",
        "asset_type": "text",
        "description": "高台、石柱、符文地面和金色烛火，适合审判、觉醒和压迫场面。",
        "tags": ["系统预置", "玄幻", "大殿", "仪式"],
        "style_tags": ["anime", "fantasy"],
        "prompt_template": "玄幻大殿，高台石柱，符文地面，金色烛火与天光，宏大压迫感。",
    },
    {
        "key": "asset-destiny-pendant-reference",
        "category": "prop",
        "name": "命运吊坠道具 DNA",
        "asset_type": "text",
        "description": "可作为主线道具的视觉 DNA：金属质感、几何轮廓、裂纹和发光符文。",
        "tags": ["系统预置", "关键道具", "吊坠"],
        "style_tags": ["anime", "mystery"],
        "prompt_template": "青铜或银色几何吊坠，细密裂纹，符文微光，近景特写，保持每次出现形状一致。",
    },
    {
        "key": "asset-battle-coat-costume",
        "category": "costume",
        "name": "现代战斗风衣",
        "asset_type": "text",
        "description": "适合都市异能、悬疑追逐和短剧主角的通用服装设定。",
        "tags": ["系统预置", "服装", "都市异能"],
        "style_tags": ["anime", "modern"],
        "prompt_template": "深色短风衣，内搭简洁，局部反光扣件，便于动作镜头，轮廓清晰。",
    },
    {
        "key": "asset-action-sfx-pack",
        "category": "sfx",
        "name": "动作镜头音效包",
        "asset_type": "text",
        "description": "适合追逐、闪避、道具发光和能量爆发的基础音效提示。",
        "tags": ["系统预置", "音效", "动作"],
        "style_tags": ["anime", "short-video"],
        "prompt_template": "脚步急促、衣料掠过、金属轻响、能量低频上升、冲击停顿。",
    },
    {
        "key": "asset-suspense-music-cue",
        "category": "music",
        "name": "悬疑推进音乐提示",
        "asset_type": "text",
        "description": "适合线索发现和结尾反转的低频铺垫音乐提示。",
        "tags": ["系统预置", "音乐", "悬疑"],
        "style_tags": ["anime", "suspense"],
        "prompt_template": "低频脉冲、轻微弦乐拨奏、逐渐上升的合成器铺底，结尾留下悬念停顿。",
    },
    {
        "key": "asset-vertical-shot-template",
        "category": "template",
        "name": "9:16 短剧三段式镜头模板",
        "asset_type": "text",
        "description": "开场钩子、冲突升级、结尾反转的轻量镜头结构。",
        "tags": ["系统预置", "9:16", "短剧", "分镜"],
        "style_tags": ["anime", "vertical-video"],
        "prompt_template": "{{hook}} -> {{conflict}} -> {{cliffhanger}}",
        "variables": [
            {"name": "hook", "type": "text"},
            {"name": "conflict", "type": "event_ref"},
            {"name": "cliffhanger", "type": "event_ref"},
        ],
        "shot_template": {
            "shot_count": 5,
            "orientation": "9:16",
            "shots": [
                {"purpose": "3秒钩子", "camera_angle": "close-up", "camera_movement": "push_in", "duration": 4},
                {"purpose": "环境交代", "camera_angle": "wide", "camera_movement": "pan", "duration": 4},
                {"purpose": "冲突升级", "camera_angle": "medium", "camera_movement": "tracking", "duration": 5},
                {"purpose": "关键道具/线索", "camera_angle": "insert", "camera_movement": "zoom_in", "duration": 4},
                {"purpose": "结尾反转", "camera_angle": "close-up", "camera_movement": "static", "duration": 4},
            ],
        },
    },
    {
        "key": "asset-xianxia-sect-scene-pack",
        "category": "scene",
        "name": "修仙宗门场景包",
        "asset_type": "text",
        "description": "仙门山门、修炼洞府、宗门大殿和云海长阶的统一视觉提示。",
        "tags": ["系统预置", "修仙", "仙侠", "宗门", "场景"],
        "style_tags": ["anime", "xianxia", "fantasy"],
        "prompt_template": "修仙宗门，云海山门、玉石长阶、古典大殿、阵法纹路、青白灵气光，保持庄严清冷的仙侠气质。",
    },
    {
        "key": "asset-xianxia-breakthrough-prompt",
        "category": "prompt",
        "name": "修仙突破提示词",
        "asset_type": "text",
        "description": "用于境界突破、雷劫和法宝护体镜头，强调灵气流向和境界变化。",
        "tags": ["系统预置", "修仙", "突破", "提示词"],
        "style_tags": ["anime", "xianxia"],
        "prompt_template": "{{character}}在{{scene}}突破境界，灵气汇聚成旋涡，{{prop}}护体发光，雷光压迫但人物造型保持一致。",
        "variables": [{"name": "character", "type": "character_ref"}, {"name": "scene", "type": "scene_ref"}, {"name": "prop", "type": "prop_ref"}],
    },
    {
        "key": "asset-wuxia-jianghu-scene-pack",
        "category": "scene",
        "name": "武侠江湖场景包",
        "asset_type": "text",
        "description": "江湖客栈、竹林山道、擂台、镖局和门派夜色的统一视觉提示。",
        "tags": ["系统预置", "武侠", "江湖", "场景"],
        "style_tags": ["anime", "wuxia"],
        "prompt_template": "武侠江湖氛围，木质客栈、竹林山道、油灯暖光、刀剑寒光、飞檐屋脊，动作利落且有侠义感。",
    },
    {
        "key": "asset-wuxia-duel-prompt",
        "category": "prompt",
        "name": "武侠刀剑对决提示词",
        "asset_type": "text",
        "description": "用于江湖对峙、轻功腾挪和刀剑交锋镜头。",
        "tags": ["系统预置", "武侠", "刀剑", "提示词"],
        "style_tags": ["anime", "wuxia"],
        "prompt_template": "{{character}}在{{scene}}施展轻功与刀剑招式，衣摆、剑光、竹影或酒旗形成动势，保持江湖写意与动作清晰。",
        "variables": [{"name": "character", "type": "character_ref"}, {"name": "scene", "type": "scene_ref"}],
    },
    {
        "key": "asset-xuanhuan-secret-realm-pack",
        "category": "scene",
        "name": "玄幻秘境场景包",
        "asset_type": "text",
        "description": "古遗迹、浮空石阶、祭坛、异兽剪影和神器能量的统一视觉提示。",
        "tags": ["系统预置", "玄幻", "秘境", "遗迹", "场景"],
        "style_tags": ["anime", "xuanhuan", "fantasy"],
        "prompt_template": "玄幻秘境，浮空石阶、古碑祭坛、断裂石柱、金蓝能量光、远处异兽剪影，画面宏大且保持道具状态一致。",
    },
    {
        "key": "asset-xuanhuan-awakening-prompt",
        "category": "prompt",
        "name": "玄幻血脉觉醒提示词",
        "asset_type": "text",
        "description": "用于血脉觉醒、灵核共鸣、神器现世和角色能力爆发。",
        "tags": ["系统预置", "玄幻", "觉醒", "提示词"],
        "style_tags": ["anime", "xuanhuan"],
        "prompt_template": "{{character}}血脉觉醒，瞳孔/手背族纹发光，{{prop}}共鸣，环境被能量纹路照亮，不改变角色年龄感和服装轮廓。",
        "variables": [{"name": "character", "type": "character_ref"}, {"name": "prop", "type": "prop_ref"}],
    },
    {
        "key": "asset-urban-power-scene-pack",
        "category": "scene",
        "name": "都市异能场景包",
        "asset_type": "text",
        "description": "地铁站台、夜巷、隐藏实验室、学校天台和监控屏的现代超自然视觉提示。",
        "tags": ["系统预置", "都市异能", "现代", "场景"],
        "style_tags": ["anime", "urban-fantasy", "neon"],
        "prompt_template": "现代城市异能氛围，地铁站台、雨夜霓虹、隐藏实验室、监控屏、手机数据异常，日常空间中出现超自然能量。",
    },
    {
        "key": "asset-urban-awakening-prompt",
        "category": "prompt",
        "name": "都市异能觉醒提示词",
        "asset_type": "text",
        "description": "用于现代城市里能力暴露、监控锁定和隐藏组织追踪。",
        "tags": ["系统预置", "都市异能", "觉醒", "提示词"],
        "style_tags": ["anime", "urban-fantasy"],
        "prompt_template": "{{character}}在{{scene}}突然觉醒能力，手机/监控/门禁卡出现异常信号，能量只短暂外泄，保持现代城市真实感。",
        "variables": [{"name": "character", "type": "character_ref"}, {"name": "scene", "type": "scene_ref"}],
    },
]


async def ensure_default_story_entities(db: AsyncSession, user_id: str) -> int:
    """Create editable default global entities for a user if missing."""
    created = 0
    for item in DEFAULT_ANIME_ENTITIES:
        evidence_key = f"starter:{item['key']}"
        result = await db.execute(
            select(StoryEntity.id).where(
                StoryEntity.user_id == user_id,
                StoryEntity.source == STARTER_SOURCE,
                StoryEntity.evidence == evidence_key,
            ).limit(1)
        )
        if result.scalar():
            continue
        attrs = dict(item.get("attributes") or {})
        attrs["starter_library_key"] = item["key"]
        attrs["starter_library"] = True
        entity = StoryEntity(
            id=str(uuid4()),
            user_id=user_id,
            novel_id=None,
            chapter_id=None,
            script_id=None,
            entity_type=item["entity_type"],
            name=item["name"],
            description=item.get("description"),
            aliases=item.get("aliases") or [],
            attributes=attrs,
            evidence=evidence_key,
            confidence=100,
            source=STARTER_SOURCE,
        )
        db.add(entity)
        created += 1
    if created:
        await db.commit()
    return created


async def ensure_default_anime_assets(db: AsyncSession, user_id: str) -> int:
    """Create editable default global assets for a user if missing."""
    created = 0
    for item in DEFAULT_ANIME_ASSETS:
        source_key = f"starter:{item['key']}"
        result = await db.execute(
            select(Asset.id).where(
                Asset.user_id == user_id,
                Asset.source_url == source_key,
            ).limit(1)
        )
        if result.scalar():
            continue
        asset = Asset(
            id=str(uuid4()),
            user_id=user_id,
            category=item["category"],
            name=item["name"],
            description=item.get("description"),
            asset_type=item.get("asset_type") or "text",
            project_id=None,
            novel_id=None,
            chapter_id=None,
            script_id=None,
            entity_id=None,
            tags=item.get("tags") or ["系统预置"],
            style_tags=item.get("style_tags") or ["anime"],
            prompt_template=item.get("prompt_template"),
            variables=item.get("variables") or [],
            shot_template=item.get("shot_template"),
            is_public=False,
            is_active=True,
            source_url=source_key,
            generation_params={
                "source": STARTER_SOURCE,
                "starter_library_key": item["key"],
                "editable": True,
            },
        )
        db.add(asset)
        created += 1
    if created:
        await db.commit()
    return created
