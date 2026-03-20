"""
API v1路由聚合
"""

from fastapi import APIRouter

from app.api.v1.endpoints import llm_config, external_api, qwen, coding_plan, usage_stats, characters, dashboard, auth, novels, scripts

api_router = APIRouter()

# 用户认证
api_router.include_router(auth.router, prefix="", tags=["用户认证"])

# 大模型配置
api_router.include_router(llm_config.router, prefix="/llm", tags=["大模型配置"])

# 外部API配置
api_router.include_router(external_api.router, prefix="/external", tags=["外部API"])

# 阿里千问API
api_router.include_router(qwen.router, prefix="/qwen", tags=["阿里千问"])

# Coding Plan API
api_router.include_router(coding_plan.router, prefix="/coding-plan", tags=["Coding Plan"])

# 使用统计API
api_router.include_router(usage_stats.router, prefix="/usage-stats", tags=["使用统计"])

# 角色管理API
api_router.include_router(characters.router, prefix="/characters", tags=["角色管理"])

# Dashboard API  
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])

# 小说管理API
api_router.include_router(novels.router, prefix="/novels", tags=["小说管理"])

# 剧本管理API
api_router.include_router(scripts.router, prefix="/scripts", tags=["剧本管理"])
