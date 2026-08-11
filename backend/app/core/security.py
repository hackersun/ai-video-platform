"""
安全模块
"""

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
import base64
import json
import re
from app.core.auth_tokens import verify_access_token
from app.core.runtime_environment import allows_development_identity

security = HTTPBearer(auto_error=False)  # auto_error=False allows optional auth

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


async def get_current_user_id(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
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
    dev_mode = allows_development_identity()
    dev_user_id = os.getenv("DEV_USER_ID", "dev-user-001")

    # 开发模式：无凭证时使用默认用户
    if dev_mode and credentials is None:
        return dev_user_id

    # 没有凭证时报错
    cookie_token = request.cookies.get("access_token")
    if credentials is None and cookie_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录后再继续操作",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials if credentials is not None else cookie_token
    assert token is not None

    if dev_mode:
        # DEV_MODE keeps compatibility with existing local/E2E tokens that only
        # carry a base64 payload.
        payload = _decode_jwt_payload(token)
        if payload and 'sub' in payload:
            return payload['sub']
        if len(token) > 36 and re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", token):
            return token[:36]
        return token

    user_id = verify_access_token(token)
    if user_id:
        return user_id

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录状态无效或已过期，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """获取当前用户信息"""
    user_id = await get_current_user_id(request, credentials)
    return {"id": user_id, "username": "dev_user"}


def get_dev_user_id() -> str:
    """获取开发模式下的默认用户ID"""
    return os.getenv("DEV_USER_ID", "dev-user-001")
