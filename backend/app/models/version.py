"""
版本历史模型
"""
from app.core.time_utils import utc_now
from sqlalchemy import Column, String, Text, Integer, DateTime, JSON, Boolean
from app.core.database import Base


class Version(Base):
    """版本历史"""
    __tablename__ = "versions"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)

    # 版本所属资源
    resource_type = Column(String(20), nullable=False, index=True)  # novel, chapter, script, storyboard, shot
    resource_id = Column(String(36), nullable=False, index=True)

    # 版本信息
    version_number = Column(Integer, nullable=False)
    version_label = Column(String(100))  # 可选标签，如"发布版本"

    # 快照数据（JSON）
    snapshot = Column(JSON)  # 保存变更前的完整数据

    # 元数据
    change_summary = Column(Text)  # 变更摘要
    created_at = Column(DateTime, default=utc_now)
    created_by = Column(String(36))

    # 索引优化
    __table_args__ = (
        # 联合索引：资源类型+资源ID+版本号（唯一）
        # 注：SQLite 不支持带表达式的唯一约束，这里用普通索引
    )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "version_number": self.version_number,
            "version_label": self.version_label,
            "change_summary": self.change_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
        }


class VersionRule(Base):
    """版本规则配置"""
    __tablename__ = "version_rules"

    resource_type = Column(String(20), primary_key=True)
    max_versions = Column(Integer, default=10)  # 最大保留版本数
    auto_snapshot = Column(Boolean, default=True)  # 是否自动快照
    auto_cleanup = Column(Boolean, default=True)  # 是否自动清理旧版本

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "resource_type": self.resource_type,
            "max_versions": self.max_versions,
            "auto_snapshot": self.auto_snapshot,
            "auto_cleanup": self.auto_cleanup,
        }