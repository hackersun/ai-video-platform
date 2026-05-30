"""
音视频合成任务模型
"""
from app.core.time_utils import utc_now
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, JSON, String, Text

from app.core.database import Base


class SynthesisJob(Base):
    """音视频合成任务"""

    __tablename__ = "synthesis_jobs"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), nullable=True, index=True)
    workflow_id = Column(String(36), nullable=True, index=True)
    task_id = Column(String(64), index=True)

    title = Column(String(200))
    model_id = Column(String(64))
    model_name = Column(String(100))
    video_url = Column(Text, nullable=False)
    audio_url = Column(Text)

    status = Column(String(20), default="pending")
    progress = Column(Integer, default=0)

    output_url = Column(Text)
    cover_url = Column(Text)
    duration_seconds = Column(Float)
    error_message = Column(Text)

    cost = Column(Integer, default=0)
    extra_data = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<SynthesisJob {self.id} status={self.status}>"
