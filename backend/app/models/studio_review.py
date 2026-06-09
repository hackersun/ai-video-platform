"""Studio 检查和返修审计模型。"""

from app.core.time_utils import utc_now
from sqlalchemy import Boolean, Column, DateTime, JSON, String, Text

from app.core.database import Base


class StudioRepairAction(Base):
    """统一创作工作台修复动作审计。"""

    __tablename__ = "studio_repair_actions"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    workflow_id = Column(String(36), nullable=False, index=True)

    code = Column(String(80), nullable=False, index=True)
    label = Column(String(120), nullable=False)
    status = Column(String(24), nullable=False, default="suggested")
    risk = Column(String(24), nullable=False, default="safe")

    source_issue_code = Column(String(120), nullable=True, index=True)
    target_type = Column(String(50), nullable=True)
    target_id = Column(String(36), nullable=True)
    params = Column(JSON, default=dict)
    result = Column(JSON, default=dict)
    error_message = Column(Text, nullable=True)

    mode = Column(String(24), default="production")
    allow_test_bypass = Column(Boolean, default=False)
    bypass_reason = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<StudioRepairAction {self.code} status={self.status} workflow={self.workflow_id}>"
