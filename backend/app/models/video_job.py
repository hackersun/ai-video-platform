"""
视频任务模型
"""
from app.core.time_utils import utc_now
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, JSON
from app.core.database import Base


class VideoJob(Base):
    """视频生成任务"""
    __tablename__ = "video_jobs"
    
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), nullable=True, index=True)
    workflow_id = Column(String(36), nullable=True, index=True)
    task_id = Column(String(64), index=True)  # 第三方任务ID
    title = Column(String(200))
    prompt = Column(Text)
    model_id = Column(String(64))
    model_name = Column(String(100))
    
    # 任务参数
    duration = Column(Integer, default=5)
    resolution = Column(String(20), default="720p")
    image_url = Column(Text)
    
    # 任务状态
    status = Column(String(20), default="pending")  # pending, running, succeeded, failed
    progress = Column(Integer, default=0)
    
    # 输出
    video_url = Column(Text)
    cover_url = Column(Text)
    error_message = Column(Text)
    
    # 消耗
    cost = Column(Integer, default=0)  # 虚拟货币
    
    # 元数据
    extra_data = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    
    def __repr__(self):
        return f"<VideoJob {self.id} status={self.status}>"
