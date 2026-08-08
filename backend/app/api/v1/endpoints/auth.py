"""
用户认证API
支持用户注册、登录、获取用户信息、令牌刷新
"""

from app.core.time_utils import utc_now
from app.core.auth_tokens import create_access_token as create_signed_access_token
from datetime import timedelta
from typing import Optional, List
from uuid import uuid4
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.runtime_environment import allows_development_identity
from app.core.security import get_current_user_id
from app.features.auth.cookies import clear_auth_cookies, set_auth_cookies
from app.features.auth.passwords import hash_password, hash_reset_token, verify_password
from app.features.auth.presenters import to_user_response
from app.features.auth.recovery_api import router as recovery_router
from app.features.auth.schemas import (
    AuthResponse,
    ChangePasswordRequest,
    MessageResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserProfileUpdateRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.models import User, UserSession
from app.services.auth_sessions import (
    InvalidRefreshToken,
    issue_session,
    revoke_all_user_sessions,
    revoke_session,
    rotate_session,
)
from app.services.auth_rate_limit import enforce_auth_rate_limit
from app.services.auth_notifications import queue_auth_notification
from app.services.password_policy import PasswordPolicyError, validate_password

router = APIRouter(tags=["用户认证"])
router.include_router(recovery_router)
logger = logging.getLogger(__name__)


# ============== JWT / bcrypt 配置 ==============

_ACCESS_TOKEN_EXPIRE_SECONDS = 15 * 60


def is_dev_mode() -> bool:
    """Return whether local development compatibility mode is enabled."""
    return allows_development_identity()


async def get_or_create_dev_user(user_id: str, db: AsyncSession) -> User:
    """Return a user, creating a local DEV_MODE placeholder when needed."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        return user

    if not is_dev_mode():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    username = user_id[:50]
    email = f"{user_id}@dev.local"
    user = User(
        id=user_id,
        username=username,
        email=email,
        hashed_password=hash_password(secrets.token_urlsafe(24)),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建JWT access token。"""
    subject = data.get("sub", data.get("user_id"))
    if not isinstance(subject, str) or not subject:
        raise ValueError("访问令牌缺少用户标识")
    return create_signed_access_token(subject, expires_delta)


# ============== API端点 ==============

@router.post("/auth/register")
async def register(
    request: UserRegisterRequest,
    http_request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Create a pending account and begin email verification."""
    await enforce_auth_rate_limit("register", http_request, request.email)
    try:
        validate_password(request.password, username=request.username, email=request.email)
    except PasswordPolicyError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    existing = await db.execute(
        select(User).where(
            (User.username == request.username) | (User.email == request.email)
        )
    )
    public_message = "注册申请已提交，请验证邮箱后登录"
    if existing.scalar_one_or_none():
        return AuthResponse(success=True, message=public_message)

    verification_token = secrets.token_urlsafe(32)
    user = User(
        id=str(uuid4()),
        username=request.username,
        email=request.email,
        hashed_password=hash_password(request.password),
        account_status="pending_verification",
        email_verification_token_hash=hash_reset_token(verification_token),
        email_verification_token_expires_at=utc_now() + timedelta(hours=24),
        is_active=False,
    )
    db.add(user)
    try:
        await db.flush()
        queue_auth_notification(
            db,
            user_id=user.id,
            recipient=user.email,
            kind="verify_email",
            token=verification_token,
        )
        await db.commit()
        await db.refresh(user)
    except Exception as error:
        await db.rollback()
        logger.exception("Registration transaction failed", exc_info=error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="注册服务暂时不可用，请稍后重试",
        ) from error

    return AuthResponse(
        success=True,
        message=public_message,
        verification_token=verification_token if is_dev_mode() else None,
    )


@router.post("/auth/login")
async def login(
    request: UserLoginRequest,
    http_request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """用户登录 - 返回access和refresh token。"""
    await enforce_auth_rate_limit("login", http_request, request.username)
    # 查找用户
    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    user = result.scalar_one_or_none()

    if not user:
        return AuthResponse(success=False, message="用户名或密码错误")

    # 验证密码
    try:
        password_ok = verify_password(request.password, user.hashed_password)
    except Exception:
        password_ok = False
    if not password_ok:
        return AuthResponse(success=False, message="用户名或密码错误")

    # 检查是否激活
    if user.account_status == "pending_verification":
        return AuthResponse(success=False, message="请先完成邮箱验证")
    if not user.is_active:
        return AuthResponse(success=False, message="账户已被禁用")

    # 生成tokens
    access_token = create_access_token(data={"sub": user.id})
    session = await issue_session(db, user.id, http_request.headers.get("user-agent"))
    refresh_token = session.refresh_token
    set_auth_cookies(response, access_token, refresh_token)

    return AuthResponse(
        success=True,
        message="登录成功",
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            avatar=user.avatar,
            created_at=user.created_at,
            is_active=user.is_active
        ),
        access_token=access_token,
        refresh_token=refresh_token if is_dev_mode() else None
    )


@router.post("/auth/refresh")
async def refresh_token(
    http_request: Request,
    response: Response,
    request: Optional[RefreshTokenRequest] = None,
    db: AsyncSession = Depends(get_db)
):
    """使用refresh token获取新的access token。"""
    presented_token = http_request.cookies.get("refresh_token") or (
        request.refresh_token if request else None
    )
    if not presented_token:
        raise HTTPException(status_code=401, detail="登录会话已过期，请重新登录")
    try:
        session = await rotate_session(
            db,
            presented_token,
            http_request.headers.get("user-agent"),
        )
    except InvalidRefreshToken as error:
        clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail=str(error)) from error

    # 验证用户仍存在且活跃
    stored_session = await db.get(UserSession, session.session_id)
    if stored_session is None:
        raise HTTPException(status_code=401, detail="登录会话无效，请重新登录")
    result = await db.execute(select(User).where(User.id == stored_session.user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用"
        )

    # 生成新的access token（保留原refresh token）
    access_token = create_access_token(data={"sub": user.id})
    set_auth_cookies(response, access_token, session.refresh_token)
    return TokenResponse(
        access_token=access_token,
        refresh_token=session.refresh_token if is_dev_mode() else None,
        expires_in=_ACCESS_TOKEN_EXPIRE_SECONDS,
    )


@router.post("/auth/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        await revoke_session(db, refresh_token)
    clear_auth_cookies(response)
    return MessageResponse(message="已安全退出登录")


@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户信息。"""
    user = await get_or_create_dev_user(user_id, db)
    return to_user_response(user)


@router.put("/auth/profile", response_model=UserResponse)
async def update_profile(
    request: UserProfileUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """更新当前用户资料。"""
    user = await get_or_create_dev_user(user_id, db)

    duplicate_username = await db.execute(
        select(User).where(User.username == request.username, User.id != user.id)
    )
    if duplicate_username.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户名已存在")

    duplicate_email = await db.execute(
        select(User).where(User.email == request.email, User.id != user.id)
    )
    if duplicate_email.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="邮箱已被注册")

    user.username = request.username
    user.email = request.email
    user.avatar = request.avatar or None
    user.updated_at = utc_now()
    await db.commit()
    await db.refresh(user)
    return to_user_response(user)


@router.post("/auth/change-password", response_model=MessageResponse)
async def change_password(
    request: ChangePasswordRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """修改当前用户密码。"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if not verify_password(request.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    if request.current_password == request.new_password:
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")
    try:
        validate_password(request.new_password, username=user.username, email=user.email)
    except PasswordPolicyError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    user.hashed_password = hash_password(request.new_password)
    user.updated_at = utc_now()
    await revoke_all_user_sessions(db, user.id)
    return MessageResponse(message="密码修改成功，请重新登录")


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    """Local support-only directory until the RBAC batch adds an admin role."""
    del user_id
    if not is_dev_mode():
        raise HTTPException(status_code=403, detail="当前账号无权查看用户目录")
    result = await db.execute(
        select(User).where(User.is_active == True).offset(skip).limit(limit)
    )
    users = result.scalars().all()

    return [to_user_response(user) for user in users]
