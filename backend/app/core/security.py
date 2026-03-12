"""
安全工具模块
JWT认证、密码哈希等
"""

from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer认证
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """获取密码哈希"""
    return pwd_context.hash(password)


def create_access_token(
    subject: Union[str, int],
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict] = None
) -> str:
    """
    创建JWT访问令牌
    
    Args:
        subject: 用户ID或其他主体标识
        expires_delta: 过期时间增量，默认使用配置中的JWT_EXPIRATION_HOURS
        extra_claims: 额外的声明数据
    
    Returns:
        JWT令牌字符串
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    
    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    }
    
    if extra_claims:
        to_encode.update(extra_claims)
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(subject: Union[str, int]) -> str:
    """
    创建JWT刷新令牌
    
    刷新令牌有效期更长，用于获取新的访问令牌
    """
    expire = datetime.utcnow() + timedelta(days=7)
    
    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """
    解码JWT令牌
    
    Args:
        token: JWT令牌字符串
    
    Returns:
        解码后的payload字典，失败返回None
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """
    获取当前用户ID（依赖注入用）
    
    用于FastAPI路由中验证用户身份
    
    Args:
        credentials: HTTP Authorization头中的凭证
    
    Returns:
        用户ID字符串
    
    Raises:
        HTTPException: 认证失败时抛出401错误
    """
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌中未找到用户标识",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 检查令牌类型
    token_type = payload.get("type")
    if token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌类型",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_id


def get_optional_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """
    可选的用户认证
    
    用于某些路由既支持认证用户又支持匿名访问的场景
    """
    if not credentials:
        return None
    
    try:
        return get_current_user_id(credentials)
    except HTTPException:
        return None


class RoleChecker:
    """
    角色权限检查器
    
    用法:
        @router.get("/admin-only", dependencies=[Depends(RoleChecker(["admin"]))])
        async def admin_endpoint():
            pass
    """
    
    def __init__(self, allowed_roles: list):
        self.allowed_roles = allowed_roles
    
    def __call__(self, user_id: str = Depends(get_current_user_id)):
        # TODO: 从数据库获取用户角色并检查
        # 这里简化处理，实际应该查询数据库
        return user_id
