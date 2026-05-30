"""
动漫制作项目模型 - 顶层容器
"""
from app.core.time_utils import utc_now
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Project(Base):
    """
    动漫制作项目 - 顶层创作容器

    一个 Project 包含:
    - 全局风格配置 (global_style, global_seed) -> 解决角色/场景漂移
    - 多个 Storyboard (分镜版本)
    - 多个 Timeline (时间线)
    - 多个 Asset (项目级资产)
    - 多个 Agent Workflow (自动化流程)
    """

    __tablename__ = "projects"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)

    # 基本信息
    name = Column(String(200), nullable=False)
    description = Column(Text)
    cover_url = Column(Text)  # 项目封面图

    # === 全局风格配置 (解决角色/场景漂移的核心) ===
    global_style = Column(String(100))  # anime, realistic, manga, watercolor, etc.
    global_seed = Column(String(500))  # 全局一致性种子词/描述
    global_negative_prompt = Column(Text)  # 全局负面提示词

    # === 角色一致性配置 ===
    character_consistency_mode = Column(
        String(20), default="seed"
    )  # seed: 种子词模式, reference: 参考图模式, ipadapter: LoRA模式
    default_character_refs = Column(JSON)  # [{"character_id": "...", "url": "..."}]

    # === 项目设置 ===
    aspect_ratio = Column(String(20), default="16:9")  # 16:9, 9:16, 1:1, 4:3
    default_fps = Column(Integer, default=24)  # 24, 25, 30, 60
    default_resolution = Column(String(20), default="1080p")  # 720p, 1080p, 4k
    default_duration = Column(Integer, default=5)  # 默认镜头时长(秒)

    # === 状态 ===
    status = Column(String(20), default="active")  # active, paused, archived, completed
    is_public = Column(Boolean, default=False)  # 是否公开

    # === 统计 ===
    novel_count = Column(Integer, default=0)
    storyboard_count = Column(Integer, default=0)
    timeline_count = Column(Integer, default=0)
    shot_count = Column(Integer, default=0)
    video_count = Column(Integer, default=0)

    # === 元数据 ===
    tags = Column(JSON)  # ["玄幻", "热血", "都市"]
    extra_data = Column(JSON)  # 扩展字段

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class ProjectMember(Base):
    """
    项目成员 - 支持多人协作
    """

    __tablename__ = "project_members"

    id = Column(String(36), primary_key=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)

    role = Column(String(20), default="editor")  # owner, editor, viewer
    is_active = Column(Boolean, default=True)

    invited_at = Column(DateTime, default=utc_now)
    joined_at = Column(DateTime)
    created_at = Column(DateTime, default=utc_now)
