"""可配置 Prompt 技能模型。"""

from app.core.time_utils import utc_now
from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text

from app.core.database import Base


class PromptSkill(Base):
    """用户可维护、可版本化的 Prompt 片段。"""

    __tablename__ = "prompt_skills"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    task = Column(String(80), nullable=False, index=True)
    stage = Column(String(80), nullable=True, index=True)
    content = Column(Text, nullable=False)
    variables = Column(JSON, default=dict)
    priority = Column(Integer, default=100)
    inject_position = Column(String(40), default="before_constraints")
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True, index=True)
    is_builtin = Column(Boolean, default=False)
    tags = Column(JSON, default=list)
    prompt_profile_version_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<PromptSkill {self.name} task={self.task} active={self.is_active}>"
