"""
Dashboard 统计 API 端点
"""

from app.core.time_utils import utc_now
from typing import List, Optional
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, union_all
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.asset import Asset
from app.models.chapter import Chapter
from app.models.character import Character
from app.models.image_job import ImageJob
from app.models.llm_config import LLMConfig, LLMModel, LLMUsageLog
from app.models.media_generation_job import MediaGenerationJob
from app.models.video_job import VideoJob
from app.models.novel import Novel
from app.models.script import Script
from app.models.shot import Shot
from app.models.storyboard import Storyboard
from app.models.synthesis_job import SynthesisJob
from app.models.tts_job import TTSJob
from app.models.activity import Activity

router = APIRouter(tags=["Dashboard"])


# ============== 辅助函数 ==============

async def log_activity(
    db: AsyncSession,
    user_id: str,
    activity_type: str,
    entity_type: str,
    entity_id: str,
    title: str,
    description: str = "",
) -> None:
    """记录用户活动"""
    activity = Activity(
        id=str(uuid4()),
        user_id=user_id,
        activity_type=activity_type,
        entity_type=entity_type,
        entity_id=entity_id,
        title=title,
        description=description,
    )
    db.add(activity)
    # 不在这里commit，由调用方统一commit


# ============== 响应模型 ==============

class DashboardStats(BaseModel):
    """Dashboard统计数据"""
    novels_count: int = 0
    scripts_count: int = 0
    characters_count: int = 0
    videos_count: int = 0
    recent_activities: List[dict] = []


class ActivityItem(BaseModel):
    """活动项"""
    id: str
    type: str
    title: str
    description: str
    timestamp: datetime


class AnalyticsContentStats(BaseModel):
    """正式内容资产统计"""
    novels_count: int = 0
    chapters_count: int = 0
    scripts_count: int = 0
    storyboards_count: int = 0
    shots_count: int = 0
    characters_count: int = 0
    assets_count: int = 0


class AnalyticsUsageSummary(BaseModel):
    """正式模型调用统计"""
    total_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    today_requests: int = 0
    today_cost: float = 0.0


class AnalyticsTaskSummary(BaseModel):
    """生成任务状态汇总"""
    total: int = 0
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    completion_rate: int = 0


class AnalyticsTaskTypeStats(BaseModel):
    """按任务类型统计"""
    type: str
    label: str
    total: int = 0
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0


class AnalyticsDailyStats(BaseModel):
    """每日趋势统计"""
    date: str
    created_tasks: int = 0
    completed_tasks: int = 0
    ai_requests: int = 0
    token_count: int = 0
    cost: float = 0.0


class AnalyticsModelUsage(BaseModel):
    """模型使用排行"""
    model_id: str
    model_name: str
    request_count: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_response_time: float = 0.0


class AnalyticsDashboardResponse(BaseModel):
    """数据分析页正式数据源"""
    data_source: str = "database"
    is_mock: bool = False
    generated_at: datetime
    period_days: int
    content_stats: AnalyticsContentStats
    usage_summary: AnalyticsUsageSummary
    task_summary: AnalyticsTaskSummary
    task_by_type: List[AnalyticsTaskTypeStats]
    daily_series: List[AnalyticsDailyStats]
    model_usage: List[AnalyticsModelUsage]
    recent_activities: List[dict] = []


# ============== API端点 ==============

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取Dashboard统计数据"""

    # 角色数量
    result = await db.execute(
        select(func.count(Character.id)).where(Character.user_id == user_id)
    )
    characters_count = result.scalar() or 0

    # 小说数量
    result = await db.execute(
        select(func.count(Novel.id)).where(Novel.user_id == user_id)
    )
    novels_count = result.scalar() or 0

    # 剧本数量
    result = await db.execute(
        select(func.count(Script.id)).where(Script.user_id == user_id)
    )
    scripts_count = result.scalar() or 0

    # 成功视频数量
    result = await db.execute(
        select(func.count(VideoJob.id)).where(
            and_(VideoJob.user_id == user_id, VideoJob.status == "succeeded")
        )
    )
    videos_count = result.scalar() or 0

    # 最近活动：从各表聚合最近5条记录
    recent_activities = await _get_recent_activities(db, user_id, limit=5)

    return DashboardStats(
        novels_count=novels_count,
        scripts_count=scripts_count,
        characters_count=characters_count,
        videos_count=videos_count,
        recent_activities=recent_activities
    )


@router.get("/analytics", response_model=AnalyticsDashboardResponse)
async def get_analytics_dashboard(
    days: int = 14,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取数据分析页正式聚合数据。

    该接口只从数据库表聚合，不返回模拟数据。前端分析页应以此接口作为唯一数据源，
    避免多接口拼装造成统计口径不一致。
    """
    safe_days = max(1, min(days, 90))
    generated_at = utc_now()

    content_stats = AnalyticsContentStats(
        novels_count=await _count_rows(db, Novel, user_id),
        chapters_count=await _count_rows(db, Chapter, user_id),
        scripts_count=await _count_rows(db, Script, user_id),
        storyboards_count=await _count_rows(db, Storyboard, user_id),
        shots_count=await _count_rows(db, Shot, user_id),
        characters_count=await _count_rows(db, Character, user_id),
        assets_count=await _count_rows(db, Asset, user_id, Asset.is_active == True),
    )

    usage_summary = await _get_analytics_usage_summary(db, user_id, generated_at)
    task_by_type = await _get_task_type_stats(db, user_id)
    task_summary = _sum_task_summary(task_by_type)
    daily_series = await _get_daily_analytics(db, user_id, safe_days, generated_at)
    model_usage = await _get_model_usage(db, user_id)
    recent_activities = await _get_recent_activities(db, user_id, limit=8)

    return AnalyticsDashboardResponse(
        generated_at=generated_at,
        period_days=safe_days,
        content_stats=content_stats,
        usage_summary=usage_summary,
        task_summary=task_summary,
        task_by_type=task_by_type,
        daily_series=daily_series,
        model_usage=model_usage,
        recent_activities=recent_activities,
    )


async def _get_recent_activities(db: AsyncSession, user_id: str, limit: int = 5) -> List[dict]:
    """聚合 Novel, Script, Character, VideoJob 表中的最近创建记录"""
    from sqlalchemy import literal

    now = utc_now()

    # Subqueries for each entity type
    novel_q = select(
        Novel.id.label("entity_id"),
        literal("novel").label("entity_type"),
        Novel.title,
        Novel.created_at,
    ).where(Novel.user_id == user_id)

    script_q = select(
        Script.id.label("entity_id"),
        literal("script").label("entity_type"),
        Script.title,
        Script.created_at,
    ).where(Script.user_id == user_id)

    char_q = select(
        Character.id.label("entity_id"),
        literal("character").label("entity_type"),
        Character.name.label("title"),
        Character.created_at,
    ).where(Character.user_id == user_id)

    video_q = select(
        VideoJob.id.label("entity_id"),
        literal("video").label("entity_type"),
        VideoJob.title,
        VideoJob.created_at,
    ).where(and_(VideoJob.user_id == user_id, VideoJob.status == "succeeded"))

    # Union all and order by created_at desc
    combined = union_all(novel_q, script_q, char_q, video_q).subquery()
    query = select(combined).order_by(combined.c.created_at.desc()).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    activities = []
    for row in rows:
        activities.append({
            "id": str(uuid4()),
            "type": f"{row.entity_type}_created",
            "title": f"创建{_entity_type_label(row.entity_type)}",
            "description": row.title or "",
            "timestamp": row.created_at.isoformat() if row.created_at else now.isoformat()
        })

    return activities


def _entity_type_label(entity_type: str) -> str:
    labels = {
        "novel": "小说",
        "script": "剧本",
        "character": "角色",
        "video": "视频",
    }
    return labels.get(entity_type, entity_type)


async def _count_rows(db: AsyncSession, model, user_id: str, *conditions) -> int:
    result = await db.execute(
        select(func.count(model.id)).where(model.user_id == user_id, *conditions)
    )
    return result.scalar() or 0


def _normalize_task_status(status: Optional[str]) -> str:
    value = (status or "pending").lower()
    if value in {"succeeded", "success", "completed", "complete", "ready"}:
        return "completed"
    if value in {"running", "generating", "processing", "in_progress"}:
        return "running"
    if value in {"failed", "error"}:
        return "failed"
    if value in {"cancelled", "canceled", "archived"}:
        return "cancelled"
    return "pending"


async def _get_analytics_usage_summary(
    db: AsyncSession,
    user_id: str,
    now: datetime,
) -> AnalyticsUsageSummary:
    result = await db.execute(
        select(
            func.count(LLMUsageLog.id).label("total_requests"),
            func.sum(LLMUsageLog.total_tokens).label("total_tokens"),
            func.sum(LLMUsageLog.cost).label("total_cost"),
        ).where(LLMUsageLog.user_id == user_id)
    )
    row = result.first()

    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_result = await db.execute(
        select(
            func.count(LLMUsageLog.id).label("today_requests"),
            func.sum(LLMUsageLog.cost).label("today_cost"),
        ).where(
            and_(
                LLMUsageLog.user_id == user_id,
                LLMUsageLog.created_at >= today,
            )
        )
    )
    today_row = today_result.first()

    return AnalyticsUsageSummary(
        total_requests=row.total_requests or 0,
        total_tokens=row.total_tokens or 0,
        total_cost=round(row.total_cost or 0.0, 4),
        today_requests=today_row.today_requests or 0,
        today_cost=round(today_row.today_cost or 0.0, 4),
    )


async def _get_task_type_stats(db: AsyncSession, user_id: str) -> List[AnalyticsTaskTypeStats]:
    task_sources = [
        ("video", "视频生成", VideoJob, [VideoJob.is_active == True]),
        ("tts", "语音合成", TTSJob, [TTSJob.is_active == True]),
        ("image", "图片生成", ImageJob, []),
        ("synthesis", "音视频合成", SynthesisJob, [SynthesisJob.is_active == True]),
        ("media", "直生音视频", MediaGenerationJob, [MediaGenerationJob.is_active == True]),
    ]
    stats: List[AnalyticsTaskTypeStats] = []

    for task_type, label, model, extra_conditions in task_sources:
        result = await db.execute(
            select(model.status, func.count(model.id))
            .where(model.user_id == user_id, *extra_conditions)
            .group_by(model.status)
        )
        counts = {
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        }
        for raw_status, count in result.all():
            counts[_normalize_task_status(raw_status)] += count or 0
        total = sum(counts.values())
        stats.append(
            AnalyticsTaskTypeStats(
                type=task_type,
                label=label,
                total=total,
                **counts,
            )
        )

    return stats


def _sum_task_summary(items: List[AnalyticsTaskTypeStats]) -> AnalyticsTaskSummary:
    summary = AnalyticsTaskSummary()
    for item in items:
        summary.total += item.total
        summary.pending += item.pending
        summary.running += item.running
        summary.completed += item.completed
        summary.failed += item.failed
        summary.cancelled += item.cancelled
    summary.completion_rate = round((summary.completed / summary.total) * 100) if summary.total else 0
    return summary


async def _get_daily_analytics(
    db: AsyncSession,
    user_id: str,
    days: int,
    now: datetime,
) -> List[AnalyticsDailyStats]:
    start_date = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    series = {
        (start_date + timedelta(days=idx)).date().isoformat(): {
            "date": (start_date + timedelta(days=idx)).date().isoformat(),
            "created_tasks": 0,
            "completed_tasks": 0,
            "ai_requests": 0,
            "token_count": 0,
            "cost": 0.0,
        }
        for idx in range(days)
    }

    task_sources = [
        (VideoJob, [VideoJob.is_active == True]),
        (TTSJob, [TTSJob.is_active == True]),
        (ImageJob, []),
        (SynthesisJob, [SynthesisJob.is_active == True]),
        (MediaGenerationJob, [MediaGenerationJob.is_active == True]),
    ]
    for model, extra_conditions in task_sources:
        result = await db.execute(
            select(
                func.date(model.created_at).label("date"),
                model.status,
                func.count(model.id).label("count"),
            )
            .where(model.user_id == user_id, model.created_at >= start_date, *extra_conditions)
            .group_by(func.date(model.created_at), model.status)
            .order_by("date")
        )
        for row in result.all():
            key = str(row.date)
            if key not in series:
                continue
            count = row.count or 0
            series[key]["created_tasks"] += count
            if _normalize_task_status(row.status) == "completed":
                series[key]["completed_tasks"] += count

    usage_result = await db.execute(
        select(
            func.date(LLMUsageLog.created_at).label("date"),
            func.count(LLMUsageLog.id).label("request_count"),
            func.sum(LLMUsageLog.total_tokens).label("token_count"),
            func.sum(LLMUsageLog.cost).label("cost"),
        )
        .where(LLMUsageLog.user_id == user_id, LLMUsageLog.created_at >= start_date)
        .group_by(func.date(LLMUsageLog.created_at))
        .order_by("date")
    )
    for row in usage_result.all():
        key = str(row.date)
        if key not in series:
            continue
        series[key]["ai_requests"] = row.request_count or 0
        series[key]["token_count"] = row.token_count or 0
        series[key]["cost"] = round(row.cost or 0.0, 4)

    return [AnalyticsDailyStats(**series[key]) for key in sorted(series)]


async def _get_model_usage(db: AsyncSession, user_id: str) -> List[AnalyticsModelUsage]:
    result = await db.execute(
        select(
            LLMUsageLog.config_id,
            func.count(LLMUsageLog.id).label("request_count"),
            func.sum(LLMUsageLog.total_tokens).label("total_tokens"),
            func.sum(LLMUsageLog.cost).label("total_cost"),
            func.avg(LLMUsageLog.response_time_ms).label("avg_response_time"),
        )
        .where(LLMUsageLog.user_id == user_id)
        .group_by(LLMUsageLog.config_id)
        .order_by(func.count(LLMUsageLog.id).desc())
        .limit(10)
    )

    rows = result.all()
    config_ids = [row.config_id for row in rows if row.config_id]
    config_names: dict[str, tuple[str, str]] = {}
    if config_ids:
        config_result = await db.execute(
            select(
                LLMConfig.id,
                LLMConfig.name,
                LLMModel.model_id,
                LLMModel.model_name,
            )
            .join(LLMModel, LLMConfig.model_id == LLMModel.id, isouter=True)
            .where(LLMConfig.id.in_(config_ids))
        )
        for config_id, config_name, model_id, model_name in config_result.all():
            config_names[config_id] = (
                model_id or config_id,
                model_name or config_name or config_id,
            )

    return [
        AnalyticsModelUsage(
            model_id=config_names.get(row.config_id, (row.config_id or "unknown", row.config_id or "unknown"))[0],
            model_name=config_names.get(row.config_id, (row.config_id or "unknown", row.config_id or "unknown"))[1],
            request_count=row.request_count or 0,
            total_tokens=row.total_tokens or 0,
            total_cost=round(row.total_cost or 0.0, 4),
            avg_response_time=round(row.avg_response_time or 0.0, 2),
        )
        for row in rows
    ]


@router.get("/activities", response_model=List[ActivityItem])
async def get_recent_activities(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取最近活动"""
    activities = await _get_recent_activities(db, user_id, limit=limit)
    return [
        ActivityItem(
            id=a["id"],
            type=a["type"],
            title=a["title"],
            description=a["description"],
            timestamp=datetime.fromisoformat(a["timestamp"])
        )
        for a in activities
    ]
