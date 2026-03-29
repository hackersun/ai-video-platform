"""
图像生成任务模型
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON
from app.core.database import Base


class ImageJob(Base):
    """图像生成任务模型"""
    __tablename__ = "image_jobs"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Generation params
    prompt = Column(Text, nullable=False)
    model = Column(String(50), nullable=False)  # Doubao-Seedream-4.5, Doubao-Seedream-5.0-lite, dall-e-3, etc.
    size = Column(String(20), nullable=True)  # 2K, 4K
    num = Column(Integer, default=1)
    style = Column(String(50), nullable=True)

    # Shot and character linkage (optional)
    shot_id = Column(String(36), ForeignKey("shots.id", ondelete="SET NULL"), nullable=True)
    character_id = Column(String(36), ForeignKey("characters.id", ondelete="SET NULL"), nullable=True)

    # Status and results
    status = Column(String(20), default="pending")  # pending, running, succeeded, failed
    image_urls = Column(JSON, default=list)  # list of generated image URLs
    task_id = Column(String(100), nullable=True)  # external service task ID
    error_message = Column(Text, nullable=True)

    # Cost tracking
    cost = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
