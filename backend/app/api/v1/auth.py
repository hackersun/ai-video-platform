"""
认证路由模块
处理用户注册、登录、登出、令牌刷新等
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user_id
)
from app.core.config import settings
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    Token,
    PasswordChange,
    PasswordReset,
    PasswordResetConfirm
)

router = APIRouter(prefix="/auth", tags=["认证"])
security = HTTPBearer()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """
    用户注册
    
    - 检查用户名和邮箱是否已存在
    - 密码哈希存储
    - 创建新用户记录
    """
    # 检查邮箱是否已存在
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被注册"
        )
    
    # 检查用户名是否已存在
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户名已被使用"
        )
    
    # 创建新用户
    try:
        new_user = User(
            email=user_data.email,
            username=user_data.username,
            nickname=user_data.nickname or user_data.username,
            hashed_password=get_password_hash(user_data.password),
            is_active=True,
            is_verified=False
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return new_user
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户创建失败，请稍后重试"
        )


@router.post("/login", response_model=Token)
async def login(
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    """
    用户登录
    
    - 支持用户名或邮箱登录
    - 验证密码
    - 生成访问令牌和刷新令牌
    - 更新最后登录时间
    """
    # 查找用户（支持用户名或邮箱）
    user = db.query(User).filter(
        (User.username == login_data.username) | (User.email == login_data.username)
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 检查用户是否被禁用
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用，请联系管理员"
        )
    
    # 验证密码
    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 更新最后登录时间
    user.last_login_at = datetime.utcnow()
    db.commit()
    
    # 生成令牌
    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={
            "username": user.username,
            "email": user.email,
            "membership": user.membership_level
        }
    )
    refresh_token = create_refresh_token(subject=str(user.id))
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_HOURS * 3600
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    刷新访问令牌
    
    - 使用刷新令牌获取新的访问令牌
    - 验证刷新令牌有效性
    - 检查用户状态
    """
    token = credentials.credentials
    payload = decode_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 检查令牌类型
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌类型",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    
    # 验证用户是否存在且活跃
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 生成新的令牌对
    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={
            "username": user.username,
            "email": user.email,
            "membership": user.membership_level
        }
    )
    new_refresh_token = create_refresh_token(subject=str(user.id))
    
    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_HOURS * 3600
    )


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    用户登出
    
    注：JWT是无状态的，这里只是记录登出行为
    实际应用中可以将令牌加入黑名单（Redis）
    """
    # TODO: 将令牌加入黑名单（Redis）
    # 这里简化处理，实际应该将令牌存入Redis黑名单
    
    return {"message": "登出成功"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    获取当前登录用户信息
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return user


@router.post("/password/change")
async def change_password(
    password_data: PasswordChange,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    修改密码
    
    - 验证旧密码
    - 更新为新密码
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 验证旧密码
    if not verify_password(password_data.old_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码错误"
        )
    
    # 更新密码
    user.hashed_password = get_password_hash(password_data.new_password)
    db.commit()
    
    return {"message": "密码修改成功"}


@router.post("/password/reset/request")
async def request_password_reset(
    reset_data: PasswordReset,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    请求密码重置
    
    - 发送重置邮件（异步任务）
    - 生成重置令牌
    """
    user = db.query(User).filter(User.email == reset_data.email).first()
    
    # 即使用户不存在也返回成功，防止邮箱枚举攻击
    if not user:
        return {"message": "如果该邮箱存在，重置邮件已发送"}
    
    # 生成重置令牌（1小时有效）
    reset_token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(hours=1),
        extra_claims={"type": "password_reset"}
    )
    
    # TODO: 发送重置邮件（异步任务）
    # background_tasks.add_task(send_reset_email, user.email, reset_token)
    
    return {"message": "如果该邮箱存在，重置邮件已发送"}


@router.post("/password/reset/confirm")
async def confirm_password_reset(
    reset_data: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """
    确认密码重置
    
    - 验证重置令牌
    - 更新密码
    """
    payload = decode_token(reset_data.token)
    
    if not payload or payload.get("type") != "password_reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效或已过期的重置令牌"
        )
    
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 更新密码
    user.hashed_password = get_password_hash(reset_data.new_password)
    db.commit()
    
    return {"message": "密码重置成功"}
