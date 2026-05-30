"""
安全模块
"""

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
import base64
import json
from jose import JWTError, jwt

security = HTTPBearer(auto_error=False)  # auto_error=False allows optional auth

_JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-in-production")
_JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


def _decode_jwt_payload(token: str) -> dict | None:
    """Decode JWT payload without verification (for development)."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        payload_b64 = parts[1] + '=' * (4 - len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:
        return None


def _verify_signed_access_token(token: str) -> str | None:
    """Verify a signed access JWT and return the subject."""
    try:
        payload = jwt.decode(token, _JWT_SECRET_KEY, algorithms=[_JWT_ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != "access":
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) and subject else None


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """
    获取当前用户ID

    开发模式：
    - 如果没有提供凭证，返回默认开发用户ID
    - 或者设置 DEV_USER_ID 环境变量来指定用户ID

    生产模式：
    - 从JWT的sub claim中提取用户ID
    """
    # 检查是否是开发模式
    dev_mode = os.getenv("DEV_MODE", "true").lower() in ("true", "1", "yes")
    dev_user_id = os.getenv("DEV_USER_ID", "dev-user-001")

    # 开发模式：无凭证时使用默认用户
    if dev_mode and credentials is None:
        return dev_user_id

    # 没有凭证时报错
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    if dev_mode:
        # DEV_MODE keeps compatibility with existing local/E2E tokens that only
        # carry a base64 payload.
        payload = _decode_jwt_payload(token)
        if payload and 'sub' in payload:
            return payload['sub']
        return token[:36] if len(token) > 36 else token

    user_id = _verify_signed_access_token(token)
    if user_id:
        return user_id

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """获取当前用户信息"""
    user_id = await get_current_user_id(credentials)
    return {"id": user_id, "username": "dev_user"}


def get_dev_user_id() -> str:
    """获取开发模式下的默认用户ID"""
    return os.getenv("DEV_USER_ID", "dev-user-001")
