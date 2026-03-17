"""
Dashboard 统计 API 端点
"""

from typing import List, Optional
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.character import Character
from app.models.llm_config import LLMConfig

router = APIRouter(tags=["Dashboard"])


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
    
    # 小说数量 (暂时返回0，后续添加Novel模型后完善)
    novels_count = 0
    
    # 剧本数量 (暂时返回0，后续添加Script模型后完善)
    scripts_count = 0
    
    # 视频数量 (暂时返回0，后续添加Video模型后完善)
    videos_count = 0
    
    # 最近活动 (模拟数据)
    recent_activities = [
        {
            "id": str(uuid4()),
            "type": "character_created",
            "title": "创建角色",
            "description": "成功创建新角色",
            "timestamp": datetime.utcnow().isoformat()
        }
    ]
    
    return DashboardStats(
        novels_count=novels_count,
        scripts_count=scripts_count,
        characters_count=characters_count,
        videos_count=videos_count,
        recent_activities=recent_activities
    )


@router.get("/activities", response_model=List[ActivityItem])
async def get_recent_activities(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取最近活动"""
    # TODO: 创建Activity模型后完善
    return [
        ActivityItem(
            id=str(uuid4()),
            type="character_created",
            title="创建角色",
            description="成功创建新角色",
            timestamp=datetime.utcnow()
        )
    ][:limit]