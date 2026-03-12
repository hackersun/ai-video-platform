"""
用户数据模型（Pydantic）
用于API请求和响应的数据验证
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ==================== 基础模型 ====================

class UserBase(BaseModel):
    """用户基础模型"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    nickname: Optional[str] = Field(None, max_length=100)
    
    model_config = ConfigDict(from_attributes=True)


class UserCreate(UserBase):
    """用户创建模型"""
    password: str = Field(..., min_length=8, max_length=100)
    
    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    """用户更新模型"""
    nickname: Optional[str] = Field(None, max_length=100)
    avatar: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=20)
    
    model_config = ConfigDict(from_attributes=True)


class UserInDB(UserBase):
    """数据库中的用户模型（包含敏感信息）"""
    id: UUID
    hashed_password: str
    phone: Optional[str] = None
    avatar: Optional[str] = None
    
    # 会员信息
    membership_level: str = "free"
    membership_expire_at: Optional[datetime] = None
    
    # 配额信息
    ai_quota_daily: int = 20
    ai_quota_used: int = 0
    storage_quota: int = 5
    storage_used: int = 0
    
    # 状态
    is_active: bool = True
    is_verified: bool = False
    is_superuser: bool = False
    
    # 时间戳
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class UserResponse(UserBase):
    """用户响应模型（返回给客户端）"""
    id: UUID
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    phone: Optional[str] = None
    
    membership_level: str = "free"
    membership_expire_at: Optional[datetime] = None
    
    ai_quota_daily: int = 20
    ai_quota_used: int = 0
    storage_quota: int = 5
    storage_used: int = 0
    
    is_active: bool = True
    is_verified: bool = False
    
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class UserProfile(UserResponse):
    """用户详细信息"""
    novel_count: int = 0
    script_count: int = 0
    video_count: int = 0
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 认证相关模型 ====================

class UserLogin(BaseModel):
    """用户登录模型"""
    username: str  # 可以是用户名或邮箱
    password: str
    
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """令牌模型"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # 秒
    
    model_config = ConfigDict(from_attributes=True)


class TokenPayload(BaseModel):
    """令牌载荷模型"""
    sub: str  # 用户ID
    exp: datetime
    iat: datetime
    type: str
    
    model_config = ConfigDict(from_attributes=True)


class PasswordChange(BaseModel):
    """密码修改模型"""
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=100)
    
    model_config = ConfigDict(from_attributes=True)


class PasswordReset(BaseModel):
    """密码重置模型"""
    email: EmailStr
    
    model_config = ConfigDict(from_attributes=True)


class PasswordResetConfirm(BaseModel):
    """密码重置确认模型"""
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 会员相关模型 ====================

class MembershipInfo(BaseModel):
    """会员信息模型"""
    level: str
    name: str
    expire_at: Optional[datetime]
    features: List[str]
    
    model_config = ConfigDict(from_attributes=True)


class QuotaInfo(BaseModel):
    """配额信息模型"""
    ai_daily: int
    ai_used: int
    ai_remaining: int
    storage_total: int
    storage_used: int
    storage_remaining: int
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 列表和分页模型 ====================

class UserListResponse(BaseModel):
    """用户列表响应"""
    items: List[UserResponse]
    total: int
    page: int
    page_size: int
    pages: int
    
    model_config = ConfigDict(from_attributes=True)
