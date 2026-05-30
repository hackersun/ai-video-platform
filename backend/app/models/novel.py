"""
小说模型
"""
from app.core.time_utils import utc_now
from sqlalchemy import Column, String, Text, Integer, DateTime, JSON, ForeignKey
from datetime import datetime
from app.core.database import Base


class Novel(Base):
    """小说模型"""
    __tablename__ = "novels"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    genre = Column(String(50))  # 玄幻、都市、仙侠等
    status = Column(String(20), default="draft")  # draft, writing, completed
    word_count = Column(Integer, default=0)
    tags = Column(JSON, default=list)
    cover_url = Column(String(500))
    source = Column(String(20), default="manual")  # manual, ai_generated
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
