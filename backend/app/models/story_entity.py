"""
Extracted story entity model.
"""

from app.core.time_utils import utc_now

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, JSON, String, Text

from app.core.database import Base


class StoryEntity(Base):
    """Characters, scenes, props and events extracted from source text."""

    __tablename__ = "story_entities"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    novel_id = Column(String(36), nullable=True, index=True)
    chapter_id = Column(String(36), nullable=True, index=True)
    script_id = Column(String(36), nullable=True, index=True)

    # 实体类型：character, scene, prop, event
    entity_type = Column(String(20), nullable=False, index=True)

    # 基本信息
    name = Column(String(200), nullable=False)
    canonical_name = Column(String(200), nullable=True)  # 规范名称
    aliases = Column(JSON, default=list)  # 别名列表
    description = Column(Text, nullable=True)

    # 视觉描述（用于图像生成）
    appearance = Column(Text, nullable=True)  # 外观描述
    visual_prompt = Column(Text, nullable=True)  # 图像生成提示词

    # 属性（兼容旧字段）
    attributes = Column(JSON, default=dict)

    # 关系
    relations = Column(JSON, default=list)  # [{"entity_id": "...", "type": "friend", "chapter_id": "..."}]

    # 状态变化
    state_changes = Column(JSON, default=list)  # [{"chapter_id": "...", "state": "...", "description": "..."}]

    # 首次出现
    first_seen_chapter_id = Column(String(36), nullable=True)

    # 原始证据（用于追溯）
    evidence = Column(Text, nullable=True)

    # 版本和一致性
    version = Column(Integer, default=1)
    is_approved = Column(Boolean, default=False)  # 是否人工确认
    consistency_score = Column(Float, default=1.0)  # 一致性评分

    # 标签
    tags = Column(JSON, default=list)

    # 额外数据
    extra_data = Column(JSON, default=dict)

    # 置信度（兼容旧字段）
    confidence = Column(Integer, default=100)
    source = Column(String(20), default="deterministic")

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
