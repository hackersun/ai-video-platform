"""
API V1路由聚合
"""

from fastapi import APIRouter

from app.api.v1 import auth, users, novels, scripts

api_router = APIRouter(prefix="/v1")

# 注册各模块路由
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(novels.router)
api_router.include_router(scripts.router)
