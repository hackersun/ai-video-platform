"""
API v1路由聚合
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, novels, health, characters, videos, tts, character_consistency, templates, assets, ai_models, teams, analytics, external_api, websocket, notifications, api_keys
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

# AI生成服务（图片/视频生成）
from app.api.v1.endpoints import ai_generation
api_router.include_router(ai_generation.router, tags=["ai-generation"])

# AI配置管理（API密钥、外部API、模型配置）
from app.api.v1.endpoints import ai_config
api_router.include_router(ai_config.router, tags=["ai-config"])

# 团队协作
api_router.include_router(teams.router, tags=["teams"])

# 数据分析
api_router.include_router(analytics.router, tags=["analytics"])

# 外部API接入
api_router.include_router(external_api.router, tags=["external-api"])

# WebSocket
api_router.include_router(websocket.router)

# 通知
api_router.include_router(notifications.router, tags=["notifications"])

# API密钥管理
api_router.include_router(api_keys.router, tags=["api-keys"])
