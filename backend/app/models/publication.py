"""
Publication/export records.
"""
from app.core.time_utils import utc_now
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, JSON, String, Text

from app.core.database import Base


class Publication(Base):
    """Local export/publication artifact record."""

    __tablename__ = "publications"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), nullable=True, index=True)
    synthesis_job_id = Column(String(36), nullable=True, index=True)

    # 基本信息
    title = Column(String(200), nullable=False)
    description = Column(Text)

    # 视频文件
    video_url = Column(String(500))
    cover_url = Column(String(500))
    duration_seconds = Column(Float)

    # 格式
    format = Column(String(20), default="mp4")  # mp4, mov, webm
    resolution = Column(String(20), default="1080p")  # 480p, 720p, 1080p
    orientation = Column(String(20), default="landscape")  # landscape, portrait

    # 发布状态
    status = Column(String(20), default="succeeded")  # draft, succeeded, published, archived

    # 可见性
    visibility = Column(String(20), default="private")  # private, project, public

    # 元数据
    tags = Column(JSON, default=list)
    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)

    # 导出相关（保留原字段以兼容）
    export_url = Column(Text)
    artifact_path = Column(Text)
    provider = Column(String(50), default="local")
    publication_metadata = Column("metadata", JSON, default=dict)

    # 时间戳
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<Publication {self.id} title={self.title} status={self.status}>"
