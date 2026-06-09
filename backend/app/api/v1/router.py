"""
API v1路由聚合
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    llm_config, external_api, qwen, coding_plan, usage_stats,
    characters, dashboard, auth, novels, scripts, video,
    chapters, storyboards, shots, synthesis, tts,
    workflow, images, assets, projects, timelines, storyboard_ai, story_bible,
    media, subtitles, short_video, production_control, graph, batch, templates, versions,
    consistency, studio,
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

# 镜头管理API
api_router.include_router(shots.router, prefix="/shots", tags=["镜头管理"])

# 视频生成API
api_router.include_router(video.router, prefix="/video", tags=["视频生成"])

# 音视频合成API
api_router.include_router(synthesis.router, prefix="/synthesis", tags=["音视频合成"])

# 语音合成API
api_router.include_router(tts.router, prefix="/tts", tags=["语音合成"])

# 工作流API
api_router.include_router(workflow.router, prefix="/workflow", tags=["工作流"])

# 图像生成API
api_router.include_router(images.router, prefix="/images", tags=["图像生成"])

# 资产库API
api_router.include_router(assets.router, prefix="/assets", tags=["资产库"])

# 项目管理API
api_router.include_router(projects.router, prefix="/projects", tags=["项目管理"])

# 时间线API
api_router.include_router(timelines.router, prefix="/timelines", tags=["时间线"])

# 分镜AI辅助API
api_router.include_router(storyboard_ai.router, prefix="/storyboard-ai", tags=["分镜AI辅助"])

# 故事圣经/一致性API
api_router.include_router(story_bible.router, prefix="/story-bibles", tags=["故事圣经"])

# 统一媒体生成API
api_router.include_router(media.router, prefix="/media", tags=["统一媒体生成"])

# 字幕轨API
api_router.include_router(subtitles.router, prefix="/subtitles", tags=["字幕轨"])

# 短视频生产API
api_router.include_router(short_video.router, prefix="/short-video", tags=["短视频生产"])

# 生产控制API
api_router.include_router(production_control.router, prefix="/production-control", tags=["生产控制"])

# 角色关系图API
api_router.include_router(graph.router, prefix="", tags=["角色关系图"])

# 批量任务API
api_router.include_router(batch.router, prefix="/batch", tags=["批量任务"])

# 模板市场API
api_router.include_router(templates.router, prefix="/templates", tags=["模板市场"])

# 版本管理API
api_router.include_router(versions.router, prefix="", tags=["版本管理"])

# 一致性检查API
api_router.include_router(consistency.router, prefix="/consistency", tags=["一致性检查"])

# 统一创作工作台API
api_router.include_router(studio.router, prefix="/studio", tags=["创作工作台"])
