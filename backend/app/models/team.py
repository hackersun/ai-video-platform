"""
团队协作模型
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, ForeignKey, DateTime, 
    Boolean, JSON, Float
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum

from app.core.database import Base


class TeamRole(str, enum.Enum):
    """团队角色"""
    OWNER = "owner"         # 所有者
    ADMIN = "admin"         # 管理员
    EDITOR = "editor"      # 编辑者
    VIEWER = "viewer"       # 查看者


class InvitationStatus(str, enum.Enum):
    """邀请状态"""
    PENDING = "pending"     # 待处理
    ACCEPTED = "accepted"   # 已接受
    EXPIRED = "expired"      # 已过期
    REJECTED = "rejected"    # 已拒绝


class Team(Base):
    """团队表"""

    __tablename__ = "teams"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    
    # 品牌定制
    logo_url = Column(String(500))
    theme_color = Column(String(7), default="#6366f1")
    
    # 设置
    settings = Column(JSON, default={})
    
    # 限额
    member_limit = Column(Integer, default=10)
    project_limit = Column(Integer, default=50)
    storage_limit = Column(Integer, default=100)  # GB
    
    # 计量
    member_count = Column(Integer, default=1)
    project_count = Column(Integer, default=0)
    storage_used = Column(Float, default=0)  # GB
    
    # 状态
    is_active = Column(Boolean, default=True)
    
    # 所有者
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    owner = relationship("User", back_populates="owned_teams")
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    projects = relationship("TeamProject", back_populates="team", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Team {self.name}>"


class TeamMember(Base):
    """团队成员表"""

    __tablename__ = "team_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 角色
    role = Column(String(20), default=TeamRole.EDITOR)
    
    # 权限
    permissions = Column(JSON, default={})  # 自定义权限
    
    # 设置
    notification_settings = Column(JSON, default={"email": True, "in_app": True})
    
    # 统计
    contribution_count = Column(Integer, default=0)  # 贡献次数
    
    # 状态
    is_active = Column(Boolean, default=True)
    
    # 时间
    joined_at = Column(DateTime, default=datetime.utcnow)
    last_active_at = Column(DateTime)
    
    # 关系
    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="team_memberships")
    
    # 唯一约束
    __table_args__ = (
        {"unique_constraint": ("team_id", "user_id")},
    )


class TeamInvitation(Base):
    """团队邀请表"""

    __tablename__ = "team_invitations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)
    
    # 邀请信息
    email = Column(String(255), nullable=False)
    role = Column(String(20), default=TeamRole.EDITOR)
    
    # 邀请人
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 状态
    status = Column(String(20), default=InvitationStatus.PENDING)
    token = Column(String(255), unique=True, nullable=False)
    
    # 过期时间
    expires_at = Column(DateTime, nullable=False)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    responded_at = Column(DateTime)
    
    # 关系
    team = relationship("Team")
    inviter = relationship("User")


class TeamProject(Base):
    """团队项目表"""

    __tablename__ = "team_projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)
    
    # 项目信息
    name = Column(String(100), nullable=False)
    description = Column(Text)
    
    # 可见性
    visibility = Column(String(20), default="team")  # private, team, public
    
    # 设置
    settings = Column(JSON, default={})
    
    # 统计
    member_count = Column(Integer, default=0)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    team = relationship("Team", back_populates="projects")


class TeamActivity(Base):
    """团队活动日志"""

    __tablename__ = "team_activities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 活动类型
    action = Column(String(50), nullable=False)  # created_project, invited_member, etc.
    resource_type = Column(String(50))  # project, member, file
    resource_id = Column(UUID(as_uuid=True))
    
    # 详情
    details = Column(JSON, default={})
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    team = relationship("Team")
    user = relationship("User")


# 更新 User 模型添加关联
# 在 User 模型中添加:
# team_memberships = relationship("TeamMember", back_populates="user")
# owned_teams = relationship("Team", back_populates="owner")