"""
剧本模型
"""
from sqlalchemy import Column, String, Text, Integer, DateTime, JSON, ForeignKey
from datetime import datetime
from app.core.database import Base


class Script(Base):
    """剧本模型"""
    __tablename__ = "scripts"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    novel_id = Column(String(36), ForeignKey("novels.id"), nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    content = Column(Text)
    genre = Column(String(50))
    style = Column(String(50))
    duration = Column(Integer)
    status = Column(String(20), default="draft")
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
