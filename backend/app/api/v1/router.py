"""
API v1路由聚合
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    llm_config, external_api, qwen, coding_plan, usage_stats,
    characters, dashboard, auth, novels, scripts, video,
    chapters, storyboards, storyboard_ai, shots, tts, synthesis,
    workflow, images, projects, assets, timelines, openai
)

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

# 章节管理API
api_router.include_router(chapters.router, prefix="/chapters", tags=["章节管理"])

# 分镜管理API
api_router.include_router(storyboards.router, prefix="/storyboards", tags=["分镜管理"])

# AI分镜生成API
api_router.include_router(storyboard_ai.router, prefix="/storyboard-ai", tags=["AI分镜生成"])

# 图像生成API
api_router.include_router(images.router, prefix="/images", tags=["图像生成"])

# 镜头管理API
api_router.include_router(shots.router, prefix="/shots", tags=["镜头管理"])

# 视频生成API
api_router.include_router(video.router, prefix="/video", tags=["视频生成"])

# TTS API
api_router.include_router(tts.router, prefix="/tts", tags=["TTS语音合成"])

# 音视频合成 API
api_router.include_router(synthesis.router, prefix="/synthesis", tags=["音视频合成"])

# 工作流 API
api_router.include_router(workflow.router, prefix="/workflow", tags=["工作流"])

# 项目管理 API
api_router.include_router(projects.router, prefix="/projects", tags=["项目管理"])

# 资产库 API
api_router.include_router(assets.router, prefix="/assets", tags=["资产库"])

# 时间线编辑 API
api_router.include_router(timelines.router, prefix="/timelines", tags=["时间线编辑"])

# OpenAI API
api_router.include_router(openai.router, prefix="/openai", tags=["OpenAI"])
