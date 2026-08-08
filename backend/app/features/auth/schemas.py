"""HTTP schemas for the authentication compatibility routes."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=1, max_length=100, description="密码")


class UserLoginRequest(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    avatar: Optional[str] = None
    created_at: datetime
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int


class AuthResponse(BaseModel):
    success: bool = True
    message: str = "成功"
    user: Optional[UserResponse] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    verification_token: Optional[str] = None
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=24, description="邮箱验证令牌")


class UserProfileUpdateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: str = Field(..., description="邮箱")
    avatar: Optional[str] = Field(None, max_length=500, description="头像URL")


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, description="当前密码")
    new_password: str = Field(..., min_length=1, max_length=100, description="新密码")


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., description="账户邮箱")


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=24, description="重置令牌")
    new_password: str = Field(..., min_length=1, max_length=100, description="新密码")


class MessageResponse(BaseModel):
    success: bool = True
    message: str
    reset_token: Optional[str] = None
