"""
模板模型
"""
from app.core.time_utils import utc_now
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, JSON, Boolean
from datetime import datetime
from app.core.database import Base


class Template(Base):
    """模板模型"""
    __tablename__ = "templates"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)

    # 模板基本信息
    name = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(50))  # genre, shot, prompt, character, scene
    tags = Column(JSON, default=list)

    # 模板内容
    content = Column(JSON)  # 模板结构数据

    # 使用统计
    usage_count = Column(Integer, default=0)
    rating = Column(Float, default=0)

    # 可见性
    is_public = Column(Boolean, default=False)
    is_featured = Column(Boolean, default=False)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


# 模板分类定义
TEMPLATE_CATEGORIES = [
    {"id": "genre", "name": "题材模板", "icon": "Book", "description": "不同类型故事的叙事框架"},
    {"id": "shot", "name": "镜头模板", "icon": "Film", "description": "常见镜头组合与节奏"},
    {"id": "prompt", "name": "提示词模板", "icon": "MessageSquare", "description": "AI生成提示词范例"},
    {"id": "character", "name": "角色模板", "icon": "Users", "description": "角色设定与背景模板"},
    {"id": "scene", "name": "场景模板", "icon": "Landscape", "description": "场景描写与氛围模板"},
]

# 预置模板数据
PRESET_TEMPLATES = [
    # 题材模板
    {
        "category": "genre",
        "name": "都市言情",
        "description": "现代都市背景的爱情故事框架",
        "tags": ["都市", "爱情", "现代"],
        "content": {
            "style": "现代都市风格",
            "typical_scenes": ["办公室", "咖啡厅", "公寓", "商场"],
            "typical_chars": ["精英男主", "职场女主", "闺蜜", "霸道总裁"],
            "plot_structure": ["相遇", "误解", "相知", "危机", "圆满"],
            "typical_tropes": ["欢喜冤家", "霸道总裁", "青梅竹马", "契约恋爱"],
        }
    },
    {
        "category": "genre",
        "name": "玄幻修仙",
        "description": "东方仙侠世界的修炼与成长",
        "tags": ["玄幻", "修仙", "东方", "升级"],
        "content": {
            "style": "东方玄幻风格",
            "typical_scenes": ["宗门", "秘境", "拍卖会", "历练之地"],
            "typical_chars": ["废柴主角", "神秘师父", "天才师兄", "妖兽伙伴"],
            "plot_structure": ["觉醒", "拜师", "试炼", "崛起", "飞升"],
            "typical_tropes": ["退婚流", "系统流", "凡人流", "丹药升级"],
        }
    },
    {
        "category": "genre",
        "name": "悬疑推理",
        "description": "充满谜题和反转的推理故事",
        "tags": ["悬疑", "推理", "刑侦", "烧脑"],
        "content": {
            "style": "悬疑推理风格",
            "typical_scenes": ["案发现场", "密室", "审讯室", "档案室"],
            "typical_chars": ["侦探", "嫌疑人", "证人", "幕后黑手"],
            "plot_structure": ["命案", "线索", "误导", "反转", "真相"],
            "typical_tropes": ["暴风雪山庄", "密室杀人", "不可能犯罪", "心理博弈"],
        }
    },
    {
        "category": "genre",
        "name": "科幻未来",
        "description": "未来科技背景的冒险故事",
        "tags": ["科幻", "未来", "赛博朋克", "星际"],
        "content": {
            "style": "科幻未来风格",
            "typical_scenes": ["太空站", "未来城市", "虚拟空间", "实验室"],
            "typical_chars": ["宇航员", "AI助手", "变异生物", "反抗军"],
            "plot_structure": ["危机", "逃亡", "发现", "抉择", "拯救"],
            "typical_tropes": ["时空旅行", "人工智能", "外星文明", "基因改造"],
        }
    },
    # 镜头模板
    {
        "category": "shot",
        "name": "对话场景",
        "description": "两人对话的经典镜头组合",
        "tags": ["对话", "双人", "正反打"],
        "content": {
            "shots": [
                {"type": "establishing", "description": "建立场景", "duration": 4},
                {"type": "over_shoulder", "description": "过肩镜头 A", "duration": 3},
                {"type": "close_up", "description": "反应镜头 B", "duration": 3},
                {"type": "close_up", "description": "反应镜头 A", "duration": 3},
                {"type": "over_shoulder", "description": "过肩镜头 B", "duration": 3},
            ]
        }
    },
    {
        "category": "shot",
        "name": "动作场景",
        "description": "展现激烈动作的镜头节奏",
        "tags": ["动作", "战斗", "运动"],
        "content": {
            "shots": [
                {"type": "wide", "description": "全景展示", "duration": 3},
                {"type": "medium", "description": "中景跟随", "duration": 4},
                {"type": "close_up", "description": "特写关键动作", "duration": 2},
                {"type": "pov", "description": "主观视角", "duration": 3},
                {"type": "slow_motion", "description": "升格慢动作", "duration": 4},
                {"type": "wide", "description": "结局全景", "duration": 3},
            ]
        }
    },
    {
        "category": "shot",
        "name": "情感高潮",
        "description": "表达强烈情感的镜头序列",
        "tags": ["情感", "高潮", "慢节奏"],
        "content": {
            "shots": [
                {"type": "close_up", "description": "面部特写", "duration": 5},
                {"type": "detail", "description": "细节镜头", "duration": 3},
                {"type": "wide", "description": "环境全景", "duration": 4},
                {"type": "close_up", "description": "眼部特写", "duration": 4},
                {"type": "slow_push", "description": "缓慢推进", "duration": 6},
            ]
        }
    },
    # 提示词模板
    {
        "category": "prompt",
        "name": "角色特写",
        "description": "角色面部与表情的提示词",
        "tags": ["人物", "特写", "表情"],
        "content": {
            "prompt": "anime style, close-up shot, {character}, {expression}, soft lighting, cinematic, high detail, 8k quality",
            "variables": {
                "character": "角色名称或描述",
                "expression": "面部表情（happy, sad, angry, surprised等）"
            }
        }
    },
    {
        "category": "prompt",
        "name": "场景氛围",
        "description": "营造特定氛围的场景提示词",
        "tags": ["场景", "氛围", "环境"],
        "content": {
            "prompt": "anime landscape, {scene_type}, {mood}, volumetric lighting, cinematic composition, {time_of_day}, {weather}, highly detailed, 8k",
            "variables": {
                "scene_type": "场景类型（forest, city, ocean, mountain等）",
                "mood": "氛围（peaceful, mysterious, dramatic, romantic等）",
                "time_of_day": "时间段（dawn, noon, dusk, night）",
                "weather": "天气（clear, rainy, foggy, snowy）"
            }
        }
    },
    {
        "category": "prompt",
        "name": "动态效果",
        "description": "展现运动和动态的提示词",
        "tags": ["动态", "运动", "特效"],
        "content": {
            "prompt": "anime style, {subject}, {action}, dynamic pose, motion blur effect, dramatic wind, flying hair, dynamic composition, cinematic lighting, high quality",
            "variables": {
                "subject": "主体（girl, boy, warrior, mage等）",
                "action": "动作（jumping, running, fighting, casting spell等）"
            }
        }
    },
    # 角色模板
    {
        "category": "character",
        "name": "主角模板",
        "description": "标准的男主角设定框架",
        "tags": ["男主", "主角", "标准"],
        "content": {
            "name_template": "{hero_name}",
            "appearance": {
                "age_range": "25-30岁",
                "build": "匀称/健壮",
                "features": ["深邃眼神", "棱角分明的脸"]
            },
            "personality": ["正直勇敢", "内心温柔", "有责任感"],
            "background": {
                "origin": "{origin_place}",
                "family": "{family_background}",
                "current_status": "{current_status}"
            },
            "special_abilities": ["{ability_1}", "{ability_2}"],
            "character_arc": ["成长", "蜕变", "承担使命"]
        }
    },
    {
        "category": "character",
        "name": "女主模板",
        "description": "标准的女主角设定框架",
        "tags": ["女主", "主角", "标准"],
        "content": {
            "name_template": "{heroine_name}",
            "appearance": {
                "age_range": "22-28岁",
                "build": "纤细/匀称",
                "features": ["明亮眼眸", "温柔气质"]
            },
            "personality": ["外表柔弱内心坚强", "聪慧独立", "重情重义"],
            "background": {
                "origin": "{origin_place}",
                "family": "{family_background}",
                "current_status": "{current_status}"
            },
            "special_abilities": ["{ability_1}", "{ability_2}"],
            "character_arc": ["觉醒", "成长", "自我实现"]
        }
    },
    {
        "category": "character",
        "name": "反派模板",
        "description": "有深度的反派角色框架",
        "tags": ["反派", "对手", "复杂"],
        "content": {
            "name_template": "{villain_name}",
            "appearance": {
                "aura": "强大压迫感/优雅危险",
                "features": ["锐利眼神", "标志性装饰"]
            },
            "personality": ["理智冷静", "追求理想", "有原则"],
            "motive": "{why_became_villain}",
            "abilities": ["{ability_1}", "{ability_2}"],
            "relationship_with_hero": "{relationship_description}"
        }
    },
    # 场景模板
    {
        "category": "scene",
        "name": "日出日落",
        "description": "展现日出日落的唯美场景",
        "tags": ["自然", "唯美", "光线"],
        "content": {
            "time": "{dawn_or_dusk}",
            "lighting": {
                "type": "volumetric",
                "color": "warm_orange_pink",
                "intensity": "soft"
            },
            "elements": ["太阳", "云彩", "剪影", "反射"],
            "camera": {
                "movement": "slow_pan",
                "composition": "rule_of_thirds"
            },
            "mood": "浪漫/感慨/希望"
        }
    },
    {
        "category": "scene",
        "name": "雨夜都市",
        "description": "雨夜城市霓虹的场景",
        "tags": ["都市", "雨夜", "赛博"],
        "content": {
            "setting": "future_city_night",
            "weather": {
                "rain": "heavy",
                "puddles": True,
                "reflections": True
            },
            "lighting": {
                "sources": ["neon_signs", "headlights", "street_lamps"],
                "colors": ["cyan", "magenta", "yellow"],
                "style": "high_contrast"
            },
            "elements": ["霓虹灯牌", "行人身影", "汽车灯光", "水面倒影"],
            "mood": "孤独/神秘/浪漫"
        }
    },
    {
        "category": "scene",
        "name": "古风庭院",
        "description": "东方古典庭院场景",
        "tags": ["古风", "东方", "庭院"],
        "content": {
            "setting": "chinese_traditional",
            "architecture": {
                "elements": ["飞檐", "雕花窗", "石灯笼", "回廊"],
                "materials": ["木材", "青瓦", "白石"]
            },
            "nature": ["竹林", "荷花池", "假山", "盆景"],
            "lighting": {
                "type": "natural_soft",
                "best_time": "morning_or_dusk"
            },
            "atmosphere": "宁静雅致", "mood": "禅意/怀旧"
        }
    },
]