"""
合成任务模型
用于音视频合成
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class SynthesisJob(Base):
    """合成任务"""
    __tablename__ = "synthesis_jobs"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # 关联的视频和音频任务
    video_job_id = Column(String(36), ForeignKey("video_jobs.id"), nullable=True)
    tts_job_id = Column(String(36), ForeignKey("tts_jobs.id"), nullable=True)
    
    # 基本信息
    title = Column(String(255), nullable=True)
    
    # 状态: pending, running, succeeded, failed
    status = Column(String(20), default="pending", index=True)
    progress = Column(Integer, default=0)  # 0-100
    
    # 输出
    output_url = Column(String(512), nullable=True)
    output_type = Column(String(20), default="mp4")  # mp4, mp3
    
    # 时长
    duration = Column(Float, nullable=True)  # 秒
    
    # 错误信息
    error_message = Column(Text, nullable=True)
    
    # 额外数据（JSON格式）
    extra_data = Column(Text, default='{}')
    
    # 成本
    cost = Column(Integer, default=0)
    
    # 是否激活
    is_active = Column(Integer, default=1)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<SynthesisJob {self.id}: {self.title} ({self.status})>"
