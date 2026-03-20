"""
用户认证API
支持用户注册、登录、获取用户信息
"""

from typing import Optional, List
from datetime import datetime
from uuid import uuid4
import hashlib
import time

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, Column, String, Boolean, DateTime, func
from pydantic import BaseModel, Field

from app.core.database import get_db, Base

router = APIRouter(tags=["用户认证"])


# ============== SQLAlchemy模型 ==============

class User(Base):
    """用户模型"""
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(128), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============== 配置 ==============

SECRET_KEY = "dev-secret-key-change-in-production"
ACCESS_TOKEN_EXPIRE_DAYS = 7


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


class AuthResponse(BaseModel):
    """认证响应"""
    success: bool
    message: str
    user: Optional[UserResponse] = None
    access_token: Optional[str] = None
    token_type: str = "bearer"


# ============== 辅助函数 ==============

def hash_password(password: str) -> str:
    """密码哈希"""
    return hashlib.sha256(f"{SECRET_KEY}{password}".encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return hash_password(plain_password) == hashed_password


def generate_token(user_id: str) -> str:
    """生成访问令牌（简化版，实际应使用JWT）"""
    timestamp = int(time.time())
    raw = f"{user_id}:{timestamp}:{SECRET_KEY}"
    return f"{user_id}_{timestamp}_{hashlib.md5(raw.encode()).hexdigest()}"


def parse_token(token: str) -> Optional[str]:
    """解析令牌获取用户ID"""
    try:
        parts = token.split("_")
        if len(parts) >= 2:
            return parts[0]
        return None
    except:
        return None


# ============== 数据库初始化 ==============

async def init_users_table(db: AsyncSession):
    """确保users表存在"""
    from sqlalchemy import text
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    await db.commit()


# ============== API端点 ==============

@router.post("/auth/register", response_model=AuthResponse)
async def register(
    request: UserRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """用户注册"""
    # 确保表存在
    await init_users_table(db)
    
    # 检查用户名是否存在
    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    if result.scalar_one_or_none():
        return AuthResponse(
            success=False,
            message="用户名已存在"
        )
    
    # 检查邮箱是否存在
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    if result.scalar_one_or_none():
        return AuthResponse(
            success=False,
            message="邮箱已被注册"
        )
    
    # 创建用户
    user = User(
        id=str(uuid4()),
        username=request.username,
        email=request.email,
        hashed_password=hash_password(request.password),
        is_active=True
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # 生成token
    token = generate_token(user.id)
    
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
        access_token=token
    )


@router.post("/auth/login", response_model=AuthResponse)
async def login(
    request: UserLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """用户登录"""
    # 确保表存在
    await init_users_table(db)
    
    # 查找用户
    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        return AuthResponse(
            success=False,
            message="用户名或密码错误"
        )
    
    # 验证密码
    if not verify_password(request.password, user.hashed_password):
        return AuthResponse(
            success=False,
            message="用户名或密码错误"
        )
    
    # 检查是否激活
    if not user.is_active:
        return AuthResponse(
            success=False,
            message="账户已被禁用"
        )
    
    # 生成token
    token = generate_token(user.id)
    
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
        access_token=token
    )


@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(
    authorization: str = Header(..., description="Bearer令牌"),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户信息"""
    # 解析token
    parts = authorization.split()
    if len(parts) != 2 or parts[0] != "Bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证格式"
        )
    
    token = parts[1]
    user_id = parse_token(token)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌"
        )
    
    # 查找用户
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
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
    """获取用户列表"""
    await init_users_table(db)
    
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
