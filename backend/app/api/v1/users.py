"""
用户路由模块
处理用户CRUD操作
"""

from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user_id, get_password_hash
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserProfile,
    UserListResponse,
    QuotaInfo
)
from app.services.user_service import user_service

router = APIRouter(prefix="/users", tags=["用户"])


@router.get("/me", response_model=UserResponse)
async def get_me(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """获取当前登录用户信息"""
    user = user_service.get_user_by_id(db, UUID(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    return user


@router.get("/me/profile", response_model=UserProfile)
async def get_my_profile(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """获取当前用户详细资料"""
    profile_data = user_service.get_user_profile(db, UUID(user_id))
    
    # 构建UserProfile响应
    user = profile_data["user"]
    return UserProfile(
        id=user.id,
        email=user.email,
        username=user.username,
        nickname=user.nickname,
        avatar=user.avatar,
        phone=user.phone,
        membership_level=user.membership_level,
        membership_expire_at=user.membership_expire_at,
        ai_quota_daily=user.ai_quota_daily,
        ai_quota_used=user.ai_quota_used,
        storage_quota=user.storage_quota,
        storage_used=user.storage_used,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
        novel_count=profile_data["novel_count"],
        script_count=profile_data["script_count"],
        video_count=profile_data["video_count"]
    )


@router.get("/me/quota", response_model=QuotaInfo)
async def get_my_quota(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """获取当前用户配额信息"""
    user = user_service.get_user_by_id(db, UUID(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return QuotaInfo(
        ai_daily=user.ai_quota_daily,
        ai_used=user.ai_quota_used,
        ai_remaining=user.ai_quota_daily - user.ai_quota_used,
        storage_total=user.storage_quota,
        storage_used=user.storage_used,
        storage_remaining=user.storage_quota - user.storage_used
    )


@router.put("/me", response_model=UserResponse)
async def update_me(
    user_data: UserUpdate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """更新当前用户信息"""
    user = user_service.update_user(db, UUID(user_id), user_data)
    return user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """注销当前用户（软删除）"""
    user_service.delete_user(db, UUID(user_id))
    return None


# ==================== 管理员接口 ====================

@router.get("", response_model=UserListResponse)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="搜索关键词"),
    is_active: Optional[bool] = Query(None),
    membership_level: Optional[str] = Query(None),
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    获取用户列表（管理员权限）
    
    - 支持分页
    - 支持搜索（用户名、邮箱、昵称）
    - 支持状态过滤
    - 支持会员等级过滤
    """
    # TODO: 检查管理员权限
    # if not is_admin(current_user_id):
    #     raise HTTPException(status_code=403, detail="权限不足")
    
    users, total = user_service.get_users(
        db,
        skip=skip,
        limit=limit,
        search=search,
        is_active=is_active,
        membership_level=membership_level
    )
    
    return UserListResponse(
        items=users,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        pages=(total + limit - 1) // limit
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """获取指定用户信息"""
    # 检查权限：只能查看自己或管理员查看所有
    if str(user_id) != current_user_id:
        # TODO: 检查管理员权限
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    user = user_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """更新指定用户信息（管理员或本人）"""
    # 检查权限
    if str(user_id) != current_user_id:
        # TODO: 检查管理员权限
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    user = user_service.update_user(db, user_id, user_data)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """删除指定用户（管理员权限）"""
    # TODO: 检查管理员权限
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="权限不足"
    )
    
    user_service.delete_user(db, user_id)
    return None


@router.post("/{user_id}/activate")
async def activate_user(
    user_id: UUID,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """激活用户（管理员权限）"""
    # TODO: 检查管理员权限
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="权限不足"
    )


@router.post("/{user_id}/deactivate")
async def deactivate_user(
    user_id: UUID,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """禁用用户（管理员权限）"""
    # TODO: 检查管理员权限
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="权限不足"
    )
