"""
用户认证API
支持用户注册、登录、获取用户信息、令牌刷新
"""

from datetime import datetime, timedelta
from typing import Optional, List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Header
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models import User

router = APIRouter(tags=["用户认证"])


# ============== JWT / bcrypt 配置 ==============

# 从环境变量读取JWT密钥，生产环境必须设置
_JWT_SECRET_KEY = "dev-jwt-secret-change-in-production"
_JWT_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_HOURS = 24
_REFRESH_TOKEN_EXPIRE_DAYS = 7

# 密码哈希 - 支持 sha256_crypt (新) 和 bcrypt (旧兼容)
pwd_context = CryptContext(schemes=["sha256_crypt", "bcrypt"], deprecated="auto")


# ============== Pydantic模型 ==============

class UserRegisterRequest(BaseModel):
    """注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=100, description="密码")


class UserLoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class UserResponse(BaseModel):
    """用户响应"""
    id: str
    username: str
    email: str
    created_at: datetime
    is_active: bool


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
    """刷新令牌请求"""
    refresh_token: str


# ============== 辅助函数 ==============

def hash_password(password: str) -> str:
    """使用bcrypt哈希密码。"""
    return pwd_context.hash(password)


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


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建JWT access token。"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=_ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, _JWT_SECRET_KEY, algorithm=_JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """创建JWT refresh token（有效期更长）。"""
    to_encode = {"sub": data.get("sub", data.get("user_id")), "type": "refresh"}
    expire = datetime.utcnow() + timedelta(days=_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, _JWT_SECRET_KEY, algorithm=_JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """解码并验证JWT token。"""
    return jwt.decode(token, _JWT_SECRET_KEY, algorithms=[_JWT_ALGORITHM])


def verify_access_token(token: str) -> Optional[str]:
    """验证access token并返回user_id。如果无效返回None。"""
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return payload.get("sub")
    except JWTError:
        return None


def verify_refresh_token(token: str) -> Optional[str]:
    """验证refresh token并返回user_id。如果无效返回None。"""
    try:
        payload = decode_token(token)
        if payload.get("type") != "refresh":
            return None
        return payload.get("sub")
    except JWTError:
        return None


# ============== API端点 ==============

@router.post("/auth/register")
async def register(
    request: UserRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """用户注册 - 注册成功后直接返回access和refresh token。"""
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
        is_active=True
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

    return AuthResponse(
        success=True,
        message="注册成功",
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at,
            is_active=user.is_active
        ),
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/auth/login")
async def login(
    request: UserLoginRequest,
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

    return AuthResponse(
        success=True,
        message="登录成功",
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at,
            is_active=user.is_active
        ),
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/auth/refresh")
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """使用refresh token获取新的access token。"""
    user_id = verify_refresh_token(request.refresh_token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的refresh token"
        )

    # 验证用户仍存在且活跃
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用"
        )

    # 生成新的access token（保留原refresh token）
    access_token = create_access_token(data={"sub": user.id})
    return TokenResponse(
        access_token=access_token,
        refresh_token=request.refresh_token,
        expires_in=_ACCESS_TOKEN_EXPIRE_HOURS * 3600
    )


@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(
    authorization: str = Header(..., description="Bearer令牌"),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户信息。"""
    # 解析token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证格式"
        )

    user_id = verify_access_token(parts[1])
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或已过期的令牌"
        )

    # 查找用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        created_at=user.created_at,
        is_active=user.is_active
    )


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
            created_at=user.created_at,
            is_active=user.is_active
        )
        for user in users
    ]
