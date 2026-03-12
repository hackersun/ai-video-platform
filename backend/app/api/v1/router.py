"""
API v1路由聚合
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, novels, health

api_router = APIRouter()

# 健康检查
api_router.include_router(health.router, prefix="/health", tags=["health"])

# 认证相关
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# 用户相关
api_router.include_router(users.router, prefix="/users", tags=["users"])

# 小说相关
api_router.include_router(novels.router, prefix="/novels", tags=["novels"])
