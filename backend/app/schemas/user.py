"""
用户Schema
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr
from uuid import UUID


class UserBase(BaseModel):
    """用户基础Schema"""
    email: EmailStr
    username: str
    nickname: Optional[str] = None
    avatar: Optional[str] = None


class UserCreate(UserBase):
    """用户创建Schema"""
    password: str


class UserUpdate(BaseModel):
    """用户更新Schema"""
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    phone: Optional[str] = None


class UserResponse(UserBase):
    """用户响应Schema"""
    id: UUID
    membership_level: str
    storage_quota: int
    storage_used: int
    is_active: bool
    is_verified: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserInDB(UserResponse):
    """数据库用户Schema"""
    hashed_password: str
    ai_quota_daily: int
    ai_quota_used: int


class Token(BaseModel):
    """Token响应"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str


class PasswordChange(BaseModel):
    """密码修改"""
    old_password: str
    new_password: str
