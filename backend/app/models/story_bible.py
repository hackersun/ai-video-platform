"""
Story Bible model for consistency across novel-to-anime production.
"""

from app.core.time_utils import utc_now
from datetime import datetime

from sqlalchemy import Column, DateTime, JSON, String, Text

from app.core.database import Base


class StoryBible(Base):
    """Project-level consistency bible."""

    __tablename__ = "story_bibles"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), nullable=True, index=True)
    novel_id = Column(String(36), nullable=True, index=True)

    title = Column(String(200), nullable=False)
    style = Column(Text)
    worldview = Column(Text)
    character_rules = Column(JSON, default=list)
    scene_rules = Column(JSON, default=list)
    prop_rules = Column(JSON, default=list)
    event_timeline = Column(JSON, default=list)
    negative_prompt = Column(Text)
    extra_data = Column(JSON, default=dict)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
