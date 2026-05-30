"""
批量任务模型
"""
from app.core.time_utils import utc_now
from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text
from app.core.database import Base


class BatchJob(Base):
    """批量任务"""
    __tablename__ = "batch_jobs"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)

    # 任务信息
    job_type = Column(String(20))  # image, tts, video
    title = Column(String(200))

    # 状态: pending, running, paused, completed, failed
    status = Column(String(20), default="pending")

    # 统计
    total_count = Column(Integer, default=0)
    pending_count = Column(Integer, default=0)
    running_count = Column(Integer, default=0)
    succeeded_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)

    # 关联
    storyboard_id = Column(String(36), index=True)
    shot_ids = Column(JSON, default=list)  # 关联的shot列表
    workflow_id = Column(String(36), nullable=True, index=True)

    # 元数据
    extra_data = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<BatchJob {self.id} type={self.job_type} status={self.status}>"


class BatchJobItem(Base):
    """批量任务项"""
    __tablename__ = "batch_job_items"

    id = Column(String(36), primary_key=True)
    batch_job_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)

    # 关联的shot
    shot_id = Column(String(36), index=True)

    # 状态: pending, running, succeeded, failed, skipped
    status = Column(String(20), default="pending")

    # 生成的媒体URL
    image_url = Column(Text)
    video_url = Column(Text)
    audio_url = Column(Text)

    # 关联的job ID
    image_job_id = Column(String(36))
    video_job_id = Column(String(36))
    tts_job_id = Column(String(36))

    # 错误信息
    error_message = Column(Text)

    # 排序
    sort_order = Column(Integer, default=0)

    # 元数据
    extra_data = Column(JSON, default=dict)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<BatchJobItem {self.id} status={self.status}>"