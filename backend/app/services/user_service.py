"""
用户服务层
处理用户相关的业务逻辑
"""

from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from fastapi import HTTPException, status

from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserProfile,
    UserListResponse
)
from app.core.security import get_password_hash, verify_password


class UserService:
    """用户服务类"""
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: UUID) -> Optional[User]:
        """根据ID获取用户"""
        return db.query(User).filter(User.id == user_id).first()
    
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        return db.query(User).filter(User.email == email).first()
    
    @staticmethod
    def get_user_by_username(db: Session, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        return db.query(User).filter(User.username == username).first()
    
    @staticmethod
    def get_users(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        membership_level: Optional[str] = None
    ) -> tuple[List[User], int]:
        """
        获取用户列表
        
        Returns:
            (用户列表, 总数)
        """
        query = db.query(User)
        
        # 搜索过滤
        if search:
            query = query.filter(
                (User.username.ilike(f"%{search}%")) |
                (User.email.ilike(f"%{search}%")) |
                (User.nickname.ilike(f"%{search}%"))
            )
        
        # 状态过滤
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        # 会员等级过滤
        if membership_level:
            query = query.filter(User.membership_level == membership_level)
        
        # 获取总数
        total = query.count()
        
        # 分页
        users = query.order_by(desc(User.created_at)).offset(skip).limit(limit).all()
        
        return users, total
    
    @staticmethod
    def create_user(db: Session, user_data: UserCreate) -> User:
        """创建用户"""
        # 检查邮箱是否已存在
        if UserService.get_user_by_email(db, user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该邮箱已被注册"
            )
        
        # 检查用户名是否已存在
        if UserService.get_user_by_username(db, user_data.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该用户名已被使用"
            )
        
        # 创建用户
        db_user = User(
            email=user_data.email,
            username=user_data.username,
            nickname=user_data.nickname or user_data.username,
            hashed_password=get_password_hash(user_data.password),
            is_active=True,
            is_verified=False
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        return db_user
    
    @staticmethod
    def update_user(
        db: Session,
        user_id: UUID,
        user_data: UserUpdate
    ) -> User:
        """更新用户信息"""
        user = UserService.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 更新字段
        update_data = user_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        
        db.commit()
        db.refresh(user)
        
        return user
    
    @staticmethod
    def delete_user(db: Session, user_id: UUID) -> bool:
        """删除用户（软删除）"""
        user = UserService.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 软删除：标记为不活跃
        user.is_active = False
        db.commit()
        
        return True
    
    @staticmethod
    def get_user_profile(db: Session, user_id: UUID) -> dict:
        """获取用户详细信息（包含统计）"""
        user = UserService.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 统计用户数据
        from app.models.novel import Novel
        from app.models.novel import Script
        
        novel_count = db.query(Novel).filter(Novel.author_id == user_id).count()
        script_count = db.query(Script).filter(
            Script.novel_id.in_(
                db.query(Novel.id).filter(Novel.author_id == user_id)
            )
        ).count()
        
        return {
            "user": user,
            "novel_count": novel_count,
            "script_count": script_count,
            "video_count": 0  # TODO: 视频统计
        }
    
    @staticmethod
    def update_quota(db: Session, user_id: UUID, quota_type: str, amount: int):
        """更新用户配额"""
        user = UserService.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        if quota_type == "ai":
            user.ai_quota_used += amount
        elif quota_type == "storage":
            user.storage_used += amount
        
        db.commit()
        db.refresh(user)
        
        return user
    
    @staticmethod
    def check_quota(db: Session, user_id: UUID, quota_type: str, required: int = 1) -> bool:
        """检查用户配额是否充足"""
        user = UserService.get_user_by_id(db, user_id)
        if not user:
            return False
        
        if quota_type == "ai":
            return (user.ai_quota_daily - user.ai_quota_used) >= required
        elif quota_type == "storage":
            return (user.storage_quota - user.storage_used) >= required
        
        return False


# 服务实例
user_service = UserService()
