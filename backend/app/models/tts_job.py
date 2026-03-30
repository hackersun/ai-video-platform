"""
TTS 语音合成任务模型
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text

from app.core.database import Base


class TTSJob(Base):
    """TTS 语音合成任务"""

    __tablename__ = "tts_jobs"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    task_id = Column(String(64), index=True)
    novel_id = Column(String(36), index=True)
    chapter_id = Column(String(36), index=True)
    script_id = Column(String(36), index=True)
    storyboard_id = Column(String(36), index=True)
    shot_id = Column(String(36), ForeignKey("shots.id", ondelete="SET NULL"), nullable=True, index=True)
    character_id = Column(String(36), ForeignKey("characters.id", ondelete="SET NULL"), nullable=True, index=True)

    title = Column(String(200))
    text = Column(Text, nullable=False)
    model_id = Column(String(64))
    model_name = Column(String(100))
    voice = Column(String(50), default="default")
    speed = Column(Float, default=1.0)
    api_provider = Column(String(20), default="minimax")

    status = Column(String(20), default="pending")
    progress = Column(Integer, default=0)
    audio_url = Column(Text)
    duration_seconds = Column(Float)
    error_message = Column(Text)

    cost = Column(Integer, default=0)
    extra_data = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<TTSJob {self.id} status={self.status}>"
