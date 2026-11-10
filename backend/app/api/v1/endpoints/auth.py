"""
用户认证API
支持用户注册、登录、获取用户信息、令牌刷新
"""

from app.core.legal import TERMS_VERSION
from app.core.time_utils import utc_now
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import uuid4
import hashlib
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import User
from app.services.password_policy import PasswordPolicyError, validate_password
from app.services.refresh_token_store import get_refresh_token_store

router = APIRouter(tags=["用户认证"])


# ============== JWT / bcrypt 配置 ==============

# 从环境变量读取JWT密钥，生产环境必须设置
_JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-in-production")
_JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
# Commercial default: short-lived access; refresh remains longer and is rotatable.
_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
_ACCESS_TOKEN_EXPIRE_HOURS = max(_ACCESS_TOKEN_EXPIRE_MINUTES, 1) / 60
_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
_RESET_TOKEN_EXPIRE_MINUTES = 30
_REFRESH_COOKIE_NAME = "avp_refresh_token"
_REFRESH_COOKIE_PATH = "/api/v1/auth"

# 密码哈希 - 支持 sha256_crypt (新) 和 bcrypt (旧兼容)
pwd_context = CryptContext(schemes=["sha256_crypt", "bcrypt"], deprecated="auto")


# ============== Pydantic模型 ==============

class UserRegisterRequest(BaseModel):
    """注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=8, max_length=100, description="密码（至少8位，含字母和数字）")
    accept_terms: bool = Field(False, description="是否同意用户协议与隐私政策")
    terms_version: Optional[str] = Field(None, max_length=40, description="同意的协议版本")


class UserLoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class UserResponse(BaseModel):
    """用户响应"""
    id: str
    username: str
    email: str
    avatar: Optional[str] = None
    created_at: datetime
    is_active: bool
    terms_accepted_version: Optional[str] = None
    terms_accepted_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    """令牌响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class AuthResponse(BaseModel):
    """认证响应（兼容前端格式）"""
    success: bool = True
    message: str = "成功"
    user: Optional[UserResponse] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求（cookie 路径可省略 body）"""
    refresh_token: Optional[str] = None


class UserProfileUpdateRequest(BaseModel):
    """资料更新请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: str = Field(..., description="邮箱")
    avatar: Optional[str] = Field(None, max_length=500, description="头像URL")


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    current_password: str = Field(..., min_length=1, description="当前密码")
    new_password: str = Field(..., min_length=8, max_length=100, description="新密码（至少8位，含字母和数字）")


class ForgotPasswordRequest(BaseModel):
    """忘记密码请求"""
    email: str = Field(..., description="账户邮箱")


class ResetPasswordRequest(BaseModel):
    """重置密码请求"""
    token: str = Field(..., min_length=24, description="重置令牌")
    new_password: str = Field(..., min_length=8, max_length=100, description="新密码（至少8位，含字母和数字）")


class MessageResponse(BaseModel):
    """通用消息响应"""
    success: bool = True
    message: str
    reset_token: Optional[str] = None


# ============== 辅助函数 ==============

def hash_password(password: str) -> str:
    """使用bcrypt哈希密码。"""
    return pwd_context.hash(password)


def hash_reset_token(token: str) -> str:
    """Hash password reset token for storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_dev_mode() -> bool:
    """Return whether local development compatibility mode is enabled (production-aware)."""
    from app.core.runtime_env import is_dev_mode as _runtime_is_dev_mode

    return _runtime_is_dev_mode()


def to_user_response(user: User) -> UserResponse:
    """Convert ORM user to API response."""
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        avatar=user.avatar,
        created_at=user.created_at,
        is_active=user.is_active,
    )


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


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码，支持 sha256_crypt, bcrypt, 以及旧 SHA256 hex 格式。"""
    import hashlib
    # 1. 先尝试 sha256_crypt
    if hashed_password.startswith('$5$'):
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            pass
    # 2. 降级：直接使用 bcrypt 验证旧哈希
    try:
        import bcrypt
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        pass
    # 3. 尝试 SHA256 hex 格式（旧数据的 64 字符格式）
    if len(hashed_password) == 64:
        try:
            import secrets
            return secrets.compare_digest(
                hashlib.sha256(plain_password.encode()).hexdigest(),
                hashed_password
            )
        except Exception:
            pass
    return False


def _access_ttl() -> timedelta:
    return timedelta(minutes=max(1, _ACCESS_TOKEN_EXPIRE_MINUTES))


def _refresh_ttl() -> timedelta:
    return timedelta(days=max(1, _REFRESH_TOKEN_EXPIRE_DAYS))


def _access_expires_in_seconds() -> int:
    return int(_access_ttl().total_seconds())


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建短时 JWT access token（默认 15 分钟）。"""
    to_encode = data.copy()
    expire = utc_now() + (expires_delta or _access_ttl())
    to_encode.update({"exp": expire, "type": "access", "iat": utc_now()})
    return jwt.encode(to_encode, _JWT_SECRET_KEY, algorithm=_JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """创建可轮换 JWT refresh token（带 jti）。"""
    to_encode = {
        "sub": data.get("sub", data.get("user_id")),
        "type": "refresh",
        "jti": secrets.token_urlsafe(16),
    }
    expire = utc_now() + _refresh_ttl()
    to_encode["exp"] = expire
    to_encode["iat"] = utc_now()
    return jwt.encode(to_encode, _JWT_SECRET_KEY, algorithm=_JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, _JWT_SECRET_KEY, algorithms=[_JWT_ALGORITHM])


def verify_access_token(token: str) -> Optional[str]:
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return payload.get("sub")
    except JWTError:
        return None


def verify_refresh_token(token: str) -> Optional[str]:
    try:
        payload = decode_token(token)
        if payload.get("type") != "refresh":
            return None
        return payload.get("sub")
    except JWTError:
        return None


def _refresh_jti(token: str) -> Optional[str]:
    try:
        payload = decode_token(token)
        if payload.get("type") != "refresh":
            return None
        jti = payload.get("jti")
        return jti if isinstance(jti, str) and jti else None
    except JWTError:
        return None


def _cookie_secure() -> bool:
    from app.core.runtime_env import is_production_environment
    return is_production_environment()


def attach_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=int(_refresh_ttl().total_seconds()),
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path=_REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_REFRESH_COOKIE_NAME, path=_REFRESH_COOKIE_PATH)


def _extract_refresh_token(request_body_token: Optional[str], http_request: Request) -> Optional[str]:
    if request_body_token and request_body_token.strip():
        return request_body_token.strip()
    cookie_token = http_request.cookies.get(_REFRESH_COOKIE_NAME)
    return cookie_token.strip() if cookie_token else None


async def _revoke_refresh_token(token: str) -> None:
    jti = _refresh_jti(token)
    if not jti:
        jti = "legacy:" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]
    await get_refresh_token_store().revoke(jti, ttl_seconds=int(_refresh_ttl().total_seconds()))


async def _assert_refresh_active(token: str) -> str:
    user_id = verify_refresh_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的refresh token")
    jti = _refresh_jti(token)
    if jti and await get_refresh_token_store().is_revoked(jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新凭证已失效，请重新登录")
    return user_id


# ============== API端点 ==============

@router.post("/auth/register")
async def register(
    request: UserRegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """用户注册 - 注册成功后直接返回access和refresh token。"""
    if not request.accept_terms:
        return AuthResponse(success=False, message="请先阅读并同意《用户协议》和《隐私政策》")
    try:
        validate_password(request.password, username=request.username, email=request.email)
    except PasswordPolicyError as exc:
        return AuthResponse(success=False, message=str(exc))
    # 检查用户名是否存在
    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    if result.scalar_one_or_none():
        return AuthResponse(success=False, message="用户名已存在")

    # 检查邮箱是否存在
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    if result.scalar_one_or_none():
        return AuthResponse(success=False, message="邮箱已被注册")

    # 创建用户
    user = User(
        id=str(uuid4()),
        username=request.username,
        email=request.email,
        hashed_password=hash_password(request.password),
        is_active=True,
        terms_accepted_version=TERMS_VERSION,
        terms_accepted_at=utc_now(),
    )
    db.add(user)
    try:
        await db.commit()
        await db.refresh(user)
    except Exception as e:
        await db.rollback()
        if "UNIQUE" in str(e).upper() or "unique" in str(e).lower():
            return AuthResponse(success=False, message="用户名或邮箱已被注册")
        return AuthResponse(success=False, message=f"注册失败: {str(e)}")

    # 生成tokens
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"user_id": user.id})

    attach_refresh_cookie(response, refresh_token)
    return AuthResponse(
        success=True,
        message="注册成功",
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            avatar=user.avatar,
            created_at=user.created_at,
            is_active=user.is_active,
            terms_accepted_version=user.terms_accepted_version,
            terms_accepted_at=user.terms_accepted_at,
        ),
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/auth/login")
async def login(
    request: UserLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """用户登录 - 返回access和refresh token。"""
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
    if not user.is_active:
        return AuthResponse(success=False, message="账户已被禁用")

    # 生成tokens
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"user_id": user.id})

    attach_refresh_cookie(response, refresh_token)
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
        refresh_token=refresh_token
    )


@router.post("/auth/refresh")
async def refresh_token(
    request: RefreshTokenRequest,
    http_request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """使用 refresh token 轮换签发新的 access + refresh。"""
    presented = _extract_refresh_token(request.refresh_token, http_request)
    if not presented:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少 refresh token")
    user_id = await _assert_refresh_active(presented)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用"
        )

    await _revoke_refresh_token(presented)
    access_token = create_access_token(data={"sub": user.id})
    new_refresh = create_refresh_token(data={"user_id": user.id})
    attach_refresh_cookie(response, new_refresh)
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=_access_expires_in_seconds()
    )


@router.post("/auth/logout", response_model=MessageResponse)
async def logout(
    request: RefreshTokenRequest,
    http_request: Request,
    response: Response,
):
    """撤销 refresh（body 或 HttpOnly cookie）并清除 cookie。"""
    presented = _extract_refresh_token(request.refresh_token, http_request)
    if presented:
        await _revoke_refresh_token(presented)
    clear_refresh_cookie(response)
    return MessageResponse(message="已退出登录")


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
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user.hashed_password = hash_password(request.new_password)
    user.updated_at = utc_now()
    await db.commit()
    return MessageResponse(message="密码修改成功")


@router.post("/auth/forgot-password", response_model=MessageResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """发起密码重置。生产环境应在邮件服务中发送重置链接。"""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    reset_token: Optional[str] = None
    if user and user.is_active:
        reset_token = secrets.token_urlsafe(32)
        user.reset_token_hash = hash_reset_token(reset_token)
        user.reset_token_expires_at = utc_now() + timedelta(minutes=_RESET_TOKEN_EXPIRE_MINUTES)
        user.updated_at = utc_now()
        await db.commit()

    response = MessageResponse(message="如果邮箱存在，系统已生成密码重置说明")
    if reset_token and is_dev_mode():
        response.reset_token = reset_token
        response.message = "DEV_MODE 已生成重置令牌，请在重置密码页面使用"
    return response


@router.post("/auth/reset-password", response_model=MessageResponse)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """使用重置令牌设置新密码。"""
    token_hash = hash_reset_token(request.token)
    result = await db.execute(select(User).where(User.reset_token_hash == token_hash))
    user = result.scalar_one_or_none()
    if not user or not user.reset_token_expires_at or user.reset_token_expires_at < utc_now():
        raise HTTPException(status_code=400, detail="重置令牌无效或已过期")
    if verify_password(request.new_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")
    try:
        validate_password(request.new_password, username=user.username, email=user.email)
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user.hashed_password = hash_password(request.new_password)
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    user.updated_at = utc_now()
    await db.commit()
    return MessageResponse(message="密码重置成功")


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    """获取用户列表。"""
    result = await db.execute(
        select(User).where(User.is_active == True).offset(skip).limit(limit)
    )
    users = result.scalars().all()

    return [
        UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            avatar=user.avatar,
            created_at=user.created_at,
            is_active=user.is_active
        )
        for user in users
    ]
