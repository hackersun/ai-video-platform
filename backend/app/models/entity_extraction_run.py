"""Entity extraction run metadata."""

from app.core.time_utils import utc_now
from sqlalchemy import Column, DateTime, JSON, String

from app.core.database import Base


class EntityExtractionRun(Base):
    """One extraction attempt over a novel/chapter/script/text source."""

    __tablename__ = "entity_extraction_runs"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    novel_id = Column(String(36), nullable=True, index=True)
    chapter_id = Column(String(36), nullable=True, index=True)
    script_id = Column(String(36), nullable=True, index=True)

    source_type = Column(String(40), nullable=False, index=True)
    source_id = Column(String(36), nullable=True, index=True)
    text_hash = Column(String(64), nullable=False, index=True)
    entity_types = Column(JSON, default=list)

    model_config_id = Column(String(36), nullable=True)
    provider = Column(String(80), nullable=True)
    model_id = Column(String(160), nullable=True)
    prompt_version = Column(String(80), nullable=True)

    status = Column(String(24), default="running", index=True)
    started_at = Column(DateTime, default=utc_now)
    completed_at = Column(DateTime, nullable=True)

    stats = Column(JSON, default=dict)
    quality_summary = Column(JSON, default=dict)
    extra_data = Column(JSON, default=dict)
