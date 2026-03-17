"""
使用统计API
支持API调用次数、token消耗、成本统计
"""

from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.llm_config import LLMUsageLog

router = APIRouter(tags=["使用统计"])


# ============== 响应模型 ==============

class UsageSummaryResponse(BaseModel):
    """使用概览响应"""
    total_requests: int
    total_tokens: int
    total_cost: float
    today_requests: int
    today_cost: float
    

class ModelUsageResponse(BaseModel):
    """模型使用统计"""
    model_id: str
    model_name: str
    request_count: int
    total_tokens: int
    total_cost: float
    avg_response_time: float


class DailyUsageResponse(BaseModel):
    """每日使用统计"""
    date: str
    request_count: int
    token_count: int
    cost: float


class UsageLogResponse(BaseModel):
    """使用日志响应"""
    id: str
    config_id: str
    model: str
    request_type: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    response_time_ms: int
    status: str
    created_at: datetime


# ============== API端点 ==============

@router.get("/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取使用概览统计"""
    # 总统计
    result = await db.execute(
        select(
            func.count(LLMUsageLog.id).label("total_requests"),
            func.sum(LLMUsageLog.total_tokens).label("total_tokens"),
            func.sum(LLMUsageLog.cost).label("total_cost")
        )
        .where(LLMUsageLog.user_id == user_id)
    )
    row = result.first()
    
    total_requests = row.total_requests or 0
    total_tokens = row.total_tokens or 0
    total_cost = row.total_cost or 0.0
    
    # 今日统计
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(
            func.count(LLMUsageLog.id).label("today_requests"),
            func.sum(LLMUsageLog.cost).label("today_cost")
        )
        .where(
            and_(
                LLMUsageLog.user_id == user_id,
                LLMUsageLog.created_at >= today
            )
        )
    )
    row = result.first()
    
    today_requests = row.today_requests or 0
    today_cost = row.today_cost or 0.0
    
    return UsageSummaryResponse(
        total_requests=total_requests,
        total_tokens=total_tokens,
        total_cost=round(total_cost, 4),
        today_requests=today_requests,
        today_cost=round(today_cost, 4)
    )


@router.get("/by-model", response_model=List[ModelUsageResponse])
async def get_usage_by_model(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """按模型统计使用情况"""
    result = await db.execute(
        select(
            LLMUsageLog.model,
            func.count(LLMUsageLog.id).label("request_count"),
            func.sum(LLMUsageLog.total_tokens).label("total_tokens"),
            func.sum(LLMUsageLog.cost).label("total_cost"),
            func.avg(LLMUsageLog.response_time_ms).label("avg_response_time")
        )
        .where(LLMUsageLog.user_id == user_id)
        .group_by(LLMUsageLog.model)
        .order_by(desc("request_count"))
    )
    
    stats = []
    for row in result.all():
        stats.append(ModelUsageResponse(
            model_id=row.model,
            model_name=row.model,  # TODO: 从模型表获取名称
            request_count=row.request_count,
            total_tokens=row.total_tokens or 0,
            total_cost=round(row.total_cost or 0, 4),
            avg_response_time=round(row.avg_response_time or 0, 2)
        ))
    
    return stats


@router.get("/daily")
async def get_daily_usage(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取每日使用统计"""
    start_date = datetime.now() - timedelta(days=days)
    
    result = await db.execute(
        select(
            func.date(LLMUsageLog.created_at).label("date"),
            func.count(LLMUsageLog.id).label("request_count"),
            func.sum(LLMUsageLog.total_tokens).label("token_count"),
            func.sum(LLMUsageLog.cost).label("cost")
        )
        .where(
            and_(
                LLMUsageLog.user_id == user_id,
                LLMUsageLog.created_at >= start_date
            )
        )
        .group_by(func.date(LLMUsageLog.created_at))
        .order_by("date")
    )
    
    daily_stats = []
    for row in result.all():
        daily_stats.append(DailyUsageResponse(
            date=str(row.date),
            request_count=row.request_count,
            token_count=row.token_count or 0,
            cost=round(row.cost or 0, 4)
        ))
    
    return daily_stats


@router.get("/logs", response_model=List[UsageLogResponse])
async def get_usage_logs(
    limit: int = 100,
    offset: int = 0,
    model: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取使用日志列表"""
    query = select(LLMUsageLog).where(LLMUsageLog.user_id == user_id)
    
    if model:
        query = query.where(LLMUsageLog.model == model)
    
    if status:
        query = query.where(LLMUsageLog.status == status)
    
    query = query.order_by(desc(LLMUsageLog.created_at)).limit(limit).offset(offset)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return [
        UsageLogResponse(
            id=log.id,
            config_id=log.config_id,
            model=log.model,
            request_type=log.request_type,
            prompt_tokens=log.prompt_tokens,
            completion_tokens=log.completion_tokens,
            total_tokens=log.total_tokens,
            cost=log.cost,
            response_time_ms=log.response_time_ms,
            status=log.status,
            created_at=log.created_at
        )
        for log in logs
    ]
