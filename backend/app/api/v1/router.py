"""
API v1路由聚合
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, novels, health, characters, videos, tts, character_consistency, templates, assets, ai_models, teams, analytics
from app.api.v1 import scripts

api_router = APIRouter()

# 健康检查
api_router.include_router(health.router, prefix="/health", tags=["health"])

# 认证相关
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# 用户相关
api_router.include_router(users.router, prefix="/users", tags=["users"])

# 小说相关
api_router.include_router(novels.router, prefix="/novels", tags=["novels"])

# 剧本相关 (scripts.py already has prefix="/scripts")
api_router.include_router(scripts.router, tags=["scripts"])

# 角色相关
api_router.include_router(characters.router, prefix="/characters", tags=["characters"])
api_router.include_router(character_consistency.router, tags=["character-consistency"])

# 视频相关
api_router.include_router(videos.router, prefix="/videos", tags=["videos"])

# 语音合成
api_router.include_router(tts.router, tags=["tts"])

# 模板库
api_router.include_router(templates.router, tags=["templates"])

# 素材库
api_router.include_router(assets.router, tags=["assets"])

# AI模型配置
api_router.include_router(ai_models.router, tags=["ai-models"])

# 团队协作
api_router.include_router(teams.router, tags=["teams"])

# 数据分析
api_router.include_router(analytics.router, tags=["analytics"])
