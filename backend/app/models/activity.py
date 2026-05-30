"""
活动记录模型
"""
from app.core.time_utils import utc_now
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from app.core.database import Base


class Activity(Base):
    """活动记录"""
    __tablename__ = "activities"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    activity_type = Column(String(50))  # created, updated, deleted, completed
    entity_type = Column(String(50))   # novel, chapter, script, storyboard, shot, video, character
    entity_id = Column(String(36), index=True)
    title = Column(String(200))
    description = Column(Text)
    created_at = Column(DateTime, default=utc_now)

    def __repr__(self):
        return f"<Activity {self.id} user={self.user_id} {self.activity_type} {self.entity_type}>"
