"""
TTS任务模型
用于语音合成任务
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class TTSJob(Base):
    """TTS任务"""
    __tablename__ = "tts_jobs"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # 关联的剧本或镜头（可选）
    script_id = Column(String(36), ForeignKey("scripts.id"), nullable=True)
    shot_id = Column(String(36), ForeignKey("shots.id"), nullable=True)
    
    # 基本信息
    title = Column(String(255), nullable=False)
    text_content = Column(Text, nullable=False)  # 要转换的文本
    
    # 语音配置
    voice_model = Column(String(50), default="default")  # 语音模型
    api_provider = Column(String(20), default="volcano")  # volcano, azure
    
    # 语音参数
    speed = Column(Float, default=1.0)  # 语速
    pitch = Column(Float, default=0)  # 音调
    
    # 状态: pending, running, succeeded, failed
    status = Column(String(20), default="pending", index=True)
    progress = Column(Integer, default=0)  # 0-100
    
    # 输出
    audio_url = Column(String(512), nullable=True)
    
    # 时长
    duration = Column(Float, nullable=True)  # 秒
    
    # 错误信息
    error_message = Column(Text, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<TTSJob {self.id}: {self.title} ({self.status})>"
