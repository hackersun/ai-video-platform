"""
用户相关端点
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.user import UserResponse, UserUpdate

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户信息"""
    # TODO: 实现获取当前用户逻辑
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
