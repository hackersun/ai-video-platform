"""
Unified media generation job model.

This table is the forward-compatible task layer for direct audio-video
generation, subtitle artifacts, timeline outputs, and future plugin adapters.
Existing VideoJob/TTSJob/SynthesisJob rows remain valid and can be linked from
source_job_ids or mirrored here as the workflow matures.
"""
from app.core.time_utils import utc_now
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, JSON, String, Text

from app.core.database import Base


class MediaGenerationJob(Base):
    """Unified media generation task."""

    __tablename__ = "media_generation_jobs"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), nullable=True, index=True)
    workflow_id = Column(String(36), nullable=True, index=True)
    task_id = Column(String(128), index=True)

    task_type = Column(String(50), nullable=False, index=True)
    media_type = Column(String(50), nullable=False, index=True)
    title = Column(String(200))
    prompt = Column(Text)

    provider_id = Column(String(50))
    model_id = Column(String(100))
    model_name = Column(String(100))
    capabilities = Column(JSON, default=list)

    novel_id = Column(String(36), nullable=True, index=True)
    chapter_id = Column(String(36), nullable=True, index=True)
    script_id = Column(String(36), nullable=True, index=True)
    storyboard_id = Column(String(36), nullable=True, index=True)
    shot_id = Column(String(36), nullable=True, index=True)

    duration_seconds = Column(Float)
    resolution = Column(String(20))
    seed = Column(Integer)

    input_assets = Column(JSON, default=list)
    source_job_ids = Column(JSON, default=dict)
    output_video_url = Column(Text)
    output_audio_url = Column(Text)
    output_manifest_url = Column(Text)
    subtitle_track_id = Column(String(36), nullable=True, index=True)
    timeline_id = Column(String(36), nullable=True, index=True)
    cover_url = Column(Text)

    status = Column(String(20), default="pending", index=True)
    progress = Column(Integer, default=0)
    error_message = Column(Text)
    quality_report = Column(JSON, default=dict)
    extra_data = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<MediaGenerationJob {self.id} type={self.task_type} status={self.status}>"
