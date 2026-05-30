"""
章节模型
"""
from app.core.time_utils import utc_now
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from datetime import datetime
from app.core.database import Base


class Chapter(Base):
    """章节模型"""
    __tablename__ = "chapters"

    id = Column(String(36), primary_key=True)
    novel_id = Column(String(36), ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text)
    chapter_number = Column(Integer, nullable=False, default=1)
    word_count = Column(Integer, default=0)
    status = Column(String(20), default="draft")  # draft, writing, completed
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
