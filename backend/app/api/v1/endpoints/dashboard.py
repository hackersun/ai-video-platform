"""
Dashboard 统计 API 端点
"""

from typing import List, Optional
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, union_all, literal_column
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.character import Character
from app.models.video_job import VideoJob
from app.models.novel import Novel
from app.models.script import Script
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


async def _get_recent_activities(db: AsyncSession, user_id: str, limit: int = 5) -> List[dict]:
    """聚合 Novel, Script, Character, VideoJob 表中的最近创建记录"""
    from sqlalchemy import literal

    now = datetime.utcnow()

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