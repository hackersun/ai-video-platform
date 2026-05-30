"""
用户模型
"""
from app.core.time_utils import utc_now
from sqlalchemy import Column, String, Boolean, DateTime
from datetime import datetime
from app.core.database import Base


class User(Base):
    """用户模型"""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False)
    avatar = Column(String(500), nullable=True)
    hashed_password = Column(String(128), nullable=False)
    reset_token_hash = Column(String(128), nullable=True)
    reset_token_expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
