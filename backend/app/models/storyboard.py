"""
分镜模型
"""
from app.core.time_utils import utc_now
from sqlalchemy import Column, String, Text, Integer, DateTime, JSON, ForeignKey
from datetime import datetime
from app.core.database import Base


class Storyboard(Base):
    """分镜模型"""
    __tablename__ = "storyboards"

    id = Column(String(36), primary_key=True)
    script_id = Column(String(36), ForeignKey("scripts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)

    # 新增：关联小说ID（用于角色一致性追踪）
    novel_id = Column(String(36), ForeignKey("novels.id", ondelete="SET NULL"), nullable=True, index=True)

    title = Column(String(200), nullable=False)
    description = Column(Text)
    content = Column(JSON)

    # 新增：风格和类型
    style = Column(String(50))      # anime, realistic, cartoon, cyberpunk, fantasy
    genre = Column(String(50))      # 小说类型

    # 新增：关联的角色ID列表（JSON格式）
    characters = Column(JSON)        # ["char_id1", "char_id2", ...]

    shot_count = Column(Integer, default=0)
    total_duration = Column(Integer, default=0)
    status = Column(String(20), default="draft")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
