"""
安全模块
"""

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os

security = HTTPBearer(auto_error=False)  # auto_error=False allows optional auth


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """
    获取当前用户ID
    
    开发模式：
    - 如果没有提供凭证，返回默认开发用户ID
    - 或者设置 DEV_USER_ID 环境变量来指定用户ID
    
    生产模式：
    - 应该使用JWT验证
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
    
    # 简化处理：直接返回token作为用户ID
    # 实际应该解析JWT
    return credentials.credentials[:36] if len(credentials.credentials) > 36 else credentials.credentials


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """获取当前用户信息"""
    user_id = await get_current_user_id(credentials)
    return {"id": user_id, "username": "dev_user"}


def get_dev_user_id() -> str:
    """获取开发模式下的默认用户ID"""
    return os.getenv("DEV_USER_ID", "dev-user-001")
