"""Evidence mentions for extracted story entities."""

from app.core.time_utils import utc_now
from sqlalchemy import Column, DateTime, Float, Integer, JSON, String

from app.core.database import Base


class StoryEntityMention(Base):
    """Evidence span linking an extraction run to a StoryEntity."""

    __tablename__ = "story_entity_mentions"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    run_id = Column(String(36), nullable=True, index=True)
    entity_id = Column(String(36), nullable=True, index=True)

    novel_id = Column(String(36), nullable=True, index=True)
    chapter_id = Column(String(36), nullable=True, index=True)
    script_id = Column(String(36), nullable=True, index=True)
    source_type = Column(String(40), nullable=True, index=True)
    source_id = Column(String(36), nullable=True, index=True)

    mention_text = Column(String(500), nullable=True)
    evidence = Column(String(1000), nullable=True)
    char_start = Column(Integer, nullable=True)
    char_end = Column(Integer, nullable=True)
    confidence = Column(Float, nullable=True)
    extractor = Column(String(40), default="deterministic")
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utc_now)
