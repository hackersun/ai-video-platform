"""
Workflow 模型 - 工作流持久化存储
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text

from app.core.database import Base


class Workflow(Base):
    """AI 视频制作工作流"""

    __tablename__ = "workflows"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    title = Column(String(200), nullable=False)
    status = Column(String(20), default="pending")  # pending, running, completed, failed

    # Pipeline links
    novel_id = Column(String(36), ForeignKey("novels.id", ondelete="SET NULL"), nullable=True, index=True)
    chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True, index=True)
    script_id = Column(String(36), ForeignKey("scripts.id", ondelete="SET NULL"), nullable=True, index=True)
    storyboard_id = Column(String(36), ForeignKey("storyboards.id", ondelete="SET NULL"), nullable=True, index=True)

    # Step tracking (1-10)
    current_step = Column(Integer, default=1)
    completed_steps = Column(JSON, default=list)  # [1, 2, 3]

    # Related job IDs
    video_job_ids = Column(JSON, default=list)
    tts_job_ids = Column(JSON, default=list)
    synthesis_job_ids = Column(JSON, default=list)

    metadata_ = Column("metadata", JSON, default=dict)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Workflow {self.id} title={self.title} status={self.status}>"
