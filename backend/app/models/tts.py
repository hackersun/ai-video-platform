"""
TTS 语音合成记录模型
"""

from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, ForeignKey, DateTime, Float
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.core.database import Base


class TTSRecord(Base):
    """TTS 生成记录表"""

    __tablename__ = "tts_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 输入内容
    text = Column(Text, nullable=False)
    text_length = Column(Integer, default=0)
    
    # 语音设置
    voice = Column(String(50), nullable=False)
    voice_name = Column(String(100))
    speed = Column(Float, default=1.0)
    pitch = Column(String(20), default="0Hz")
    volume = Column(String(10), default="0%")
    
    # 输出结果
    audio_url = Column(String(500))
    file_path = Column(String(500))
    file_size = Column(Integer, default=0)
    duration = Column(Float, default=0)
    
    # 状态
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    error_message = Column(Text)
    
    # 关联
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    script_id = Column(UUID(as_uuid=True), ForeignKey("scripts.id"), nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<TTSRecord {self.id} {self.voice_name}>"