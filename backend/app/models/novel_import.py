"""
Novel import job model.
"""

from app.core.time_utils import utc_now
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text

from app.core.database import Base


class NovelImportJob(Base):
    """Persistent preview state for imported novel files."""

    __tablename__ = "novel_import_jobs"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100))
    status = Column(String(20), default="previewed", nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    chapter_count = Column(Integer, default=0)
    word_count = Column(Integer, default=0)
    metadata_json = Column(JSON, default=dict)
    chapters_preview = Column(JSON, default=list)
    novel_id = Column(String(36), nullable=True, index=True)
    error_message = Column(Text)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
