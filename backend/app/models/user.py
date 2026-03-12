"""
用户模型
"""

from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
import uuid

from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    # 用户信息
    nickname = Column(String(100))
    avatar = Column(String(500))
    phone = Column(String(20))
    
    # 会员信息
    membership_level = Column(String(20), default="free")  # free, pro, team, enterprise
    membership_expire_at = Column(DateTime)
    
    # 配额信息
    ai_quota_daily = Column(Integer, default=20)
    ai_quota_used = Column(Integer, default=0)
    storage_quota = Column(Integer, default=5)  # GB
    storage_used = Column(Integer, default=0)  # GB
    
    # 状态
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_superuser = Column(Boolean, default=False)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime)
    
    # 关系
    novels = relationship("Novel", back_populates="author")
    
    def __repr__(self):
        return f"<User {self.username}>"
