"""
Subtitle track and segment models.

Subtitles are first-class production assets: editable, exportable, and tied to
story/shot lineage rather than being only transient manifest fields.
"""
from app.core.time_utils import utc_now
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, JSON, String, Text

from app.core.database import Base


class SubtitleTrack(Base):
    """A language/kind-specific subtitle track."""

    __tablename__ = "subtitle_tracks"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), nullable=True, index=True)
    workflow_id = Column(String(36), nullable=True, index=True)
    novel_id = Column(String(36), nullable=True, index=True)
    chapter_id = Column(String(36), nullable=True, index=True)
    script_id = Column(String(36), nullable=True, index=True)
    storyboard_id = Column(String(36), nullable=True, index=True)
    shot_id = Column(String(36), nullable=True, index=True)
    media_job_id = Column(String(36), nullable=True, index=True)

    title = Column(String(200))
    language = Column(String(20), default="zh-CN")
    kind = Column(String(50), default="dialogue")
    source = Column(String(50), default="shot_dialogue")
    status = Column(String(20), default="draft")
    export_urls = Column(JSON, default=dict)
    metadata_ = Column("metadata", JSON, default=dict)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<SubtitleTrack {self.id} language={self.language} status={self.status}>"


class SubtitleSegment(Base):
    """A timed subtitle segment."""

    __tablename__ = "subtitle_segments"

    id = Column(String(36), primary_key=True)
    track_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    shot_id = Column(String(36), nullable=True, index=True)
    speaker_entity_id = Column(String(36), nullable=True, index=True)
    speaker_name = Column(String(100))

    start_seconds = Column(Float, default=0.0)
    end_seconds = Column(Float, default=0.0)
    text = Column(Text, nullable=False)
    original_text = Column(Text)
    source = Column(String(50), default="shot_dialogue")
    confidence = Column(Float)
    review_status = Column(String(20), default="pending_review")
    style = Column(JSON, default=dict)
    metadata_ = Column("metadata", JSON, default=dict)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<SubtitleSegment {self.id} track={self.track_id}>"
