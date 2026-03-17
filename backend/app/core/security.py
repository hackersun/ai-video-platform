"""
安全模块
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os

security = HTTPBearer()


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """
    获取当前用户ID
    
    简化版本：从token中解析用户ID
    实际生产环境需要JWT验证
    
    开发模式：可设置 DEV_USER_ID 环境变量跳过认证
    """
    # 开发环境跳过认证
    dev_user_id = os.getenv("DEV_USER_ID")
    if dev_user_id:
        return dev_user_id
    
    # 简化处理：直接返回token作为用户ID
    # 实际应该解析JWT
    return credentials.credentials[:36] if len(credentials.credentials) > 36 else credentials.credentials


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """获取当前用户信息"""
    user_id = await get_current_user_id(credentials)
    return {"id": user_id, "username": "user"}
