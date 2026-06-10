"""
资产库模型 - 角色/场景/道具/服装/提示词模板等
支持项目资产库 + 全局资产库双层复用
"""
from app.core.time_utils import utc_now
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class AssetCategory(Base):
    """
    资产分类定义
    """

    __tablename__ = "asset_categories"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)  # character, scene, prop, costume, music, sfx, template, prompt
    name_cn = Column(String(100))  # 中文名: 角色, 场景, 道具, 服装, 音乐, 音效, 模板, 提示词
    icon = Column(String(50))  # lucide 图标名
    sort_order = Column(Integer, default=0)
    parent_id = Column(String(36), ForeignKey("asset_categories.id"), nullable=True)
    is_system = Column(Boolean, default=False)  # 系统内置分类不可删除
    created_at = Column(DateTime, default=utc_now)


# 预置分类数据
DEFAULT_CATEGORIES = [
    {"name": "character", "name_cn": "角色", "icon": "Users", "sort_order": 1},
    {"name": "scene", "name_cn": "场景", "icon": "Landscape", "sort_order": 2},
    {"name": "prop", "name_cn": "道具", "icon": "Box", "sort_order": 3},
    {"name": "costume", "name_cn": "服装", "icon": "Shirt", "sort_order": 4},
    {"name": "pose", "name_cn": "姿势", "icon": "PersonStanding", "sort_order": 5},
    {"name": "expression", "name_cn": "表情", "icon": "Smile", "sort_order": 6},
    {"name": "style", "name_cn": "风格", "icon": "Palette", "sort_order": 7},
    {"name": "aspect_ratio", "name_cn": "画面比例", "icon": "PanelsTopLeft", "sort_order": 8},
    {"name": "effect", "name_cn": "特效", "icon": "Sparkles", "sort_order": 9},
    {"name": "voice", "name_cn": "音色", "icon": "Mic", "sort_order": 10},
    {"name": "music", "name_cn": "音乐", "icon": "Music", "sort_order": 11},
    {"name": "sfx", "name_cn": "音效", "icon": "Volume2", "sort_order": 12},
    {"name": "template", "name_cn": "模板", "icon": "Layout", "sort_order": 13},
    {"name": "prompt", "name_cn": "提示词", "icon": "MessageSquare", "sort_order": 14},
]


class Asset(Base):
    """
    资产 - 可复用的创作单元

    project_id = NULL 表示全局资产(模板市场)
    project_id = 具体ID 表示项目级资产
    """

    __tablename__ = "assets"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)

    # === 资产类型 ===
    category = Column(String(50), nullable=False)  # character, scene, prop, costume, music, sfx, template, prompt
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # === 资产内容 ===
    asset_type = Column(String(50))  # image, video, audio, text, lora, ipadapter
    url = Column(Text)  # 主要资源URL
    thumbnail_url = Column(Text)  # 缩略图
    file_size = Column(Integer)  # 文件大小(字节)

    # === 角色特有字段 ===
    character_id = Column(String(36), ForeignKey("characters.id", ondelete="SET NULL"), nullable=True)
    expressions = Column(JSON)  # [{"name": "happy", "url": "https://...", "description": "开心表情"}]
    poses = Column(JSON)  # [{"name": "walking", "url": "https://...", "description": "行走姿态"}]

    # === 标签和搜索 ===
    tags = Column(JSON)  # ["玄幻", "室内", "战斗"]
    style_tags = Column(JSON)  # ["anime", "realistic"]
    color_tags = Column(JSON)  # [{"name": "红色", "hex": "#FF0000"}]

    # === 关联项目 ===
    project_id = Column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )  # NULL = 全局资产
    novel_id = Column(String(36), nullable=True, index=True)
    chapter_id = Column(String(36), nullable=True, index=True)
    script_id = Column(String(36), nullable=True, index=True)
    entity_id = Column(String(36), nullable=True, index=True)
    entity_type = Column(String(20), nullable=True)  # character, scene, prop, event

    # === 提示词模板 ===
    prompt_template = Column(Text)  # "{{character}}在{{scene}}中{{action}}"
    variables = Column(JSON)  # [{"name": "character", "type": "character_ref"}, {"name": "scene", "type": "scene_ref"}]

    # === 镜头模板专用 ===
    shot_template = Column(JSON)  # {"shot_count": 6, "shots": [...]}

    # === 评分和使用 ===
    likes = Column(Integer, default=0)
    usage_count = Column(Integer, default=0)  # 被使用的次数
    rating = Column(Float, default=0.0)  # 平均评分

    # === 可见性 ===
    is_public = Column(Boolean, default=False)  # 是否公开到模板市场
    is_active = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)  # 是否精选

    # === 版本管理 ===
    version = Column(Integer, default=1)  # 版本号
    is_locked = Column(Boolean, default=False)  # 是否锁定
    locked_at = Column(DateTime, nullable=True)
    locked_by = Column(String(36), nullable=True)  # 锁定用户ID

    # === 定稿标志 ===
    is_final = Column(Boolean, default=False)  # 是否是定稿
    replaced_by_id = Column(String(36), nullable=True)  # 被哪个版本替代

    # === 来源追踪 ===
    source_url = Column(Text, nullable=True)  # 外部来源或系统预置唯一来源键
    source_job_id = Column(String(36), nullable=True)  # 生成此资产的job ID
    source_prompt = Column(Text, nullable=True)  # 生成时的prompt
    generation_params = Column(JSON, nullable=True)  # 生成参数和系统预置信息

    # === 时间戳 ===
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
