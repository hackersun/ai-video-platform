"""
用户相关端点
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.schemas.user import UserResponse, UserUpdate
from app.models.user import User

router = APIRouter()


def get_current_user_from_token(token: str) -> str:
    """从Token获取用户名"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        return username
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户信息"""
    # 简化实现：返回固定用户
    # TODO: 从JWT token获取用户并查询数据库
    return UserResponse(
        id="df9f3e6c-63ef-4e29-bdd1-130f2579ca23",
        email="test@example.com",
        username="testuser",
        nickname="测试用户",
        avatar=None,
        phone=None,
        membership_level="free",
        membership_expire_at=None,
        ai_quota_daily=20,
        ai_quota_used=0,
        storage_quota=5,
        storage_used=0,
        is_active=True,
        is_verified=False,
        created_at="2026-03-12T12:25:31",
        updated_at="2026-03-12T12:25:31",
        last_login_at=None
    )


@router.put("/me", response_model=UserResponse)
async def update_user(
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新当前用户信息"""
    # TODO: 实现用户更新逻辑
    return {
        "id": "test-uuid",
        "email": "test@example.com",
        "username": "testuser",
        "membership_level": "free",
        "storage_quota": 5,
        "storage_used": 0,
        "is_active": True,
        "is_verified": False,
        "created_at": "2024-01-01T00:00:00"
    }


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取指定用户信息"""
    # TODO: 实现获取用户逻辑
    raise HTTPException(status_code=404, detail="用户不存在")
