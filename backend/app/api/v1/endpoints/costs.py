"""
成本API端点
支持成本估算、使用统计、预算管理
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, or_, case
from pydantic import BaseModel
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import Shot, Storyboard, ImageJob, VideoJob, TTSJob, SynthesisJob
from app.services.cost_calculator import get_cost_calculator


router = APIRouter(prefix="/costs", tags=["成本预算"])


# ============== 响应模型 ==============

class CostEstimateResponse(BaseModel):
    """成本估算响应"""
    resource_type: str
    resource_id: Optional[str] = None
    estimated_cost: float
    parameters: Dict[str, Any] = {}
    message: str = ""


class CostSummaryResponse(BaseModel):
    """成本概览响应"""
    period: str
    total_cost: float
    by_type: Dict[str, float] = {}
    by_date: List[Dict[str, Any]] = []


class CostBreakdownResponse(BaseModel):
    """成本明细响应"""
    text_cost: float = 0.0
    image_cost: float = 0.0
    video_cost: float = 0.0
    tts_cost: float = 0.0
    synthesis_cost: float = 0.0
    total: float = 0.0
    item_count: Dict[str, int] = {}


class BudgetSettingRequest(BaseModel):
    """预算设置请求"""
    monthly_limit: float
    warning_threshold: float = 0.8  # 警告阈值（百分比）


class BudgetSettingResponse(BaseModel):
    """预算设置响应"""
    monthly_limit: float
    warning_threshold: float
    current_usage: float
    usage_percentage: float
    is_warning: bool


class ResourceCostRequest(BaseModel):
    """资源成本估算请求"""
    resource_type: str  # text/image/video/tts/synthesis
    count: int = 1
    duration: Optional[int] = None  # 视频时长(秒) 或 TTS字符数
    resolution: str = "medium"
    custom_price: Optional[float] = None


# ============== 辅助函数 ==============

async def get_shot_by_id(db: AsyncSession, shot_id: str, user_id: str) -> Optional[Shot]:
    """获取镜头"""
    result = await db.execute(
        select(Shot).where(Shot.id == shot_id, Shot.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_storyboard_with_shots(db: AsyncSession, storyboard_id: str, user_id: str) -> tuple:
    """获取分镜及其镜头"""
    result = await db.execute(
        select(Storyboard).where(
            Storyboard.id == storyboard_id,
            Storyboard.user_id == user_id
        )
    )
    storyboard = result.scalar_one_or_none()
    if not storyboard:
        return None, []

    shots_result = await db.execute(
        select(Shot)
        .where(Shot.storyboard_id == storyboard_id, Shot.user_id == user_id)
        .order_by(Shot.shot_number)
    )
    shots = shots_result.scalars().all()
    return storyboard, shots


def normalize_task_status(status: Optional[str]) -> str:
    """标准化任务状态"""
    value = (status or "pending").lower()
    if value in {"succeeded", "success", "completed", "complete", "ready"}:
        return "completed"
    if value in {"running", "generating", "processing", "in_progress"}:
        return "running"
    if value in {"failed", "error"}:
        return "failed"
    return "pending"


# ============== 成本估算API ==============

@router.get("/estimate/{resource_type}", response_model=CostEstimateResponse)
async def estimate_resource_cost(
    resource_type: str,
    count: int = Query(1, ge=1, le=100),
    duration: Optional[int] = Query(None, ge=1, le=60),
    resolution: str = Query("medium", pattern="^(low|medium|high|480p|720p|1080p)$"),
    model_id: Optional[str] = Query(None),
    frame_rate: int = Query(24, ge=1, le=120),
    input_video_duration: float = Query(0, ge=0, le=3600),
    price_per_million_tokens: Optional[float] = Query(None, ge=0),
    input_tokens: Optional[int] = Query(None, ge=0),
    output_tokens: Optional[int] = Query(None, ge=0),
    char_count: Optional[int] = Query(None, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    预估资源成本

    - text: 需要 input_tokens 和 output_tokens
    - image: 需要 count 和 resolution (low/medium/high)
    - video: 需要 count, duration(秒), resolution(480p/720p/1080p)
    - tts: 需要 char_count
    - synthesis: 可选 duration
    """
    calculator = get_cost_calculator()

    parameters = {"count": count}

    if resource_type == "text":
        if input_tokens is None or output_tokens is None:
            raise HTTPException(400, "text类型需要 input_tokens 和 output_tokens 参数")
        parameters["input_tokens"] = input_tokens
        parameters["output_tokens"] = output_tokens
        cost = calculator.estimate_text_cost(input_tokens, output_tokens)
        message = f"文本生成: {input_tokens} 输入 + {output_tokens} 输出 tokens"

    elif resource_type == "image":
        parameters["resolution"] = resolution
        cost = calculator.estimate_image_cost(count=count, resolution=resolution)
        message = f"图像生成: {count} 张 ({resolution})"

    elif resource_type == "video":
        if duration is None:
            raise HTTPException(400, "video类型需要 duration 参数（秒）")
        parameters["duration"] = duration
        parameters["resolution"] = resolution
        if model_id:
            parameters["model_id"] = model_id
        parameters["frame_rate"] = frame_rate
        if input_video_duration:
            parameters["input_video_duration"] = input_video_duration
        if price_per_million_tokens is not None:
            parameters["price_per_million_tokens"] = price_per_million_tokens
        billing_units = calculator.estimate_video_billing_units(
            model_id=model_id,
            count=count,
            duration=duration,
            resolution=resolution,
            frame_rate=frame_rate,
            input_video_duration=input_video_duration,
        )
        if billing_units:
            parameters["billing_units"] = billing_units
        cost = calculator.estimate_video_cost(
            count=count,
            duration=duration,
            resolution=resolution,
            model_id=model_id,
            frame_rate=frame_rate,
            input_video_duration=input_video_duration,
            price_per_million_tokens=price_per_million_tokens,
        )
        message = f"视频生成: {count} 个 ({duration}s, {resolution})"

    elif resource_type == "tts":
        if char_count is None:
            raise HTTPException(400, "tts类型需要 char_count 参数")
        parameters["char_count"] = char_count
        cost = calculator.estimate_tts_cost(char_count=char_count)
        message = f"TTS语音合成: {char_count} 字符"

    elif resource_type == "synthesis":
        if duration:
            parameters["duration"] = duration
        cost = calculator.estimate_synthesis_cost(duration=duration)
        message = f"音视频合成" + (f" ({duration}s)" if duration else "")

    else:
        raise HTTPException(400, f"不支持的资源类型: {resource_type}")

    return CostEstimateResponse(
        resource_type=resource_type,
        estimated_cost=cost,
        parameters=parameters,
        message=message,
    )


@router.get("/estimate/shot/{shot_id}")
async def estimate_shot_cost(
    shot_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """预估单个镜头成本（图像+视频+TTS）"""
    shot = await get_shot_by_id(db, shot_id, user_id)
    if not shot:
        raise HTTPException(404, "镜头不存在")

    calculator = get_cost_calculator()
    estimate = calculator.estimate_shot_cost(shot)

    return {
        "shot_id": shot_id,
        "cost_estimate": estimate.to_dict(),
        "message": f"镜头预估成本: ¥{estimate.total_cost:.4f}",
    }


@router.get("/estimate/storyboard/{storyboard_id}")
async def estimate_storyboard_cost(
    storyboard_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """预估整个分镜成本"""
    storyboard, shots = await get_storyboard_with_shots(db, storyboard_id, user_id)
    if not storyboard:
        raise HTTPException(404, "分镜不存在")

    calculator = get_cost_calculator()
    estimate = await calculator.estimate_storyboard_cost(storyboard, shots)

    return {
        "storyboard_id": storyboard_id,
        "storyboard_title": storyboard.title,
        "shot_count": len(shots),
        "cost_estimate": estimate.to_dict(),
        "message": f"分镜预估成本: ¥{estimate.total_cost:.4f} ({len(shots)}个镜头)",
    }


# ============== 使用统计API ==============

@router.get("/usage/{period}", response_model=CostSummaryResponse)
async def get_cost_usage(
    period: str = Path(..., pattern="^(day|week|month)$"),
    days: Optional[int] = Query(None, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    获取使用统计

    - day: 今天
    - week: 最近7天
    - month: 最近30天（或指定days）
    """
    calculator = get_cost_calculator()

    # 确定时间范围
    now = datetime.now()
    if period == "day":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start_date = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        days_count = days or 30
        start_date = (now - timedelta(days=days_count)).replace(hour=0, minute=0, second=0, microsecond=0)

    by_type: Dict[str, float] = {
        "text": 0.0,
        "image": 0.0,
        "video": 0.0,
        "tts": 0.0,
        "synthesis": 0.0,
    }

    # LLM使用成本（文本）
    llm_result = await db.execute(
        select(func.sum(LLMUsageLog.cost))
        .where(
            LLMUsageLog.user_id == user_id,
            LLMUsageLog.created_at >= start_date
        )
    )
    llm_cost = llm_result.scalar() or 0.0
    by_type["text"] = round(llm_cost, 4)

    # 图像生成成本
    image_result = await db.execute(
        select(
            func.count(ImageJob.id).label("count"),
            func.sum(ImageJob.cost)
        )
        .where(
            ImageJob.user_id == user_id,
            ImageJob.created_at >= start_date,
            ImageJob.status == "succeeded"
        )
    )
    image_row = image_result.first()
    by_type["image"] = round(float(image_row.sum or 0), 4)

    # 视频生成成本
    video_result = await db.execute(
        select(
            func.count(VideoJob.id).label("count"),
            func.sum(VideoJob.cost)
        )
        .where(
            VideoJob.user_id == user_id,
            VideoJob.created_at >= start_date,
            VideoJob.status == "succeeded"
        )
    )
    video_row = video_result.first()
    by_type["video"] = round(float(video_row.sum or 0) / 100, 4)  # 虚拟货币转元

    # TTS成本
    tts_result = await db.execute(
        select(
            func.count(TTSJob.id).label("count"),
            func.sum(TTSJob.cost)
        )
        .where(
            TTSJob.user_id == user_id,
            TTSJob.created_at >= start_date,
            TTSJob.status == "succeeded"
        )
    )
    tts_row = tts_result.first()
    by_type["tts"] = round(float(tts_row.sum or 0) / 100, 4)

    # 合成成本
    synth_result = await db.execute(
        select(
            func.count(SynthesisJob.id).label("count"),
            func.sum(SynthesisJob.cost)
        )
        .where(
            SynthesisJob.user_id == user_id,
            SynthesisJob.created_at >= start_date,
            SynthesisJob.status == "succeeded"
        )
    )
    synth_row = synth_result.first()
    by_type["synthesis"] = round(float(synth_row.sum or 0) / 100, 4)

    # 每日明细
    by_date = []
    date_range = []
    current = start_date
    while current <= now:
        date_range.append(current.date().isoformat())
        current += timedelta(days=1)

    for date_str in date_range:
        by_date.append({
            "date": date_str,
            "cost": 0.0,
        })

    total_cost = sum(by_type.values())

    return CostSummaryResponse(
        period=period,
        total_cost=round(total_cost, 4),
        by_type=by_type,
        by_date=by_date,
    )


@router.get("/breakdown", response_model=CostBreakdownResponse)
async def get_cost_breakdown(
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取成本明细统计"""
    start_date = datetime.now() - timedelta(days=days)

    # 文本成本（LLM使用）
    llm_result = await db.execute(
        select(
            func.count(LLMUsageLog.id).label("count"),
            func.sum(LLMUsageLog.cost).label("cost")
        )
        .where(
            LLMUsageLog.user_id == user_id,
            LLMUsageLog.created_at >= start_date
        )
    )
    llm_row = llm_result.first()
    text_cost = round(llm_row.cost or 0, 4)
    text_count = llm_row.count or 0

    # 图像成本
    image_result = await db.execute(
        select(
            func.count(ImageJob.id).label("count"),
            func.sum(ImageJob.cost)
        )
        .where(
            ImageJob.user_id == user_id,
            ImageJob.created_at >= start_date,
            ImageJob.status == "succeeded"
        )
    )
    image_row = image_result.first()
    image_cost = round(float(image_row.sum or 0), 4)
    image_count = image_row.count or 0

    # 视频成本
    video_result = await db.execute(
        select(
            func.count(VideoJob.id).label("count"),
            func.sum(VideoJob.cost).label("cost")
        )
        .where(
            VideoJob.user_id == user_id,
            VideoJob.created_at >= start_date,
            VideoJob.status == "succeeded"
        )
    )
    video_row = video_result.first()
    video_cost = round(float(video_row.cost or 0) / 100, 4)
    video_count = video_row.count or 0

    # TTS成本
    tts_result = await db.execute(
        select(
            func.count(TTSJob.id).label("count"),
            func.sum(TTSJob.cost).label("cost")
        )
        .where(
            TTSJob.user_id == user_id,
            TTSJob.created_at >= start_date,
            TTSJob.status == "succeeded"
        )
    )
    tts_row = tts_result.first()
    tts_cost = round(float(tts_row.cost or 0) / 100, 4)
    tts_count = tts_row.count or 0

    # 合成成本
    synth_result = await db.execute(
        select(
            func.count(SynthesisJob.id).label("count"),
            func.sum(SynthesisJob.cost).label("cost")
        )
        .where(
            SynthesisJob.user_id == user_id,
            SynthesisJob.created_at >= start_date,
            SynthesisJob.status == "succeeded"
        )
    )
    synth_row = synth_result.first()
    synth_cost = round(float(synth_row.cost or 0) / 100, 4)
    synth_count = synth_row.count or 0

    total = text_cost + image_cost + video_cost + tts_cost + synth_cost

    return CostBreakdownResponse(
        text_cost=text_cost,
        image_cost=image_cost,
        video_cost=video_cost,
        tts_cost=tts_cost,
        synthesis_cost=synth_cost,
        total=round(total, 4),
        item_count={
            "text": text_count,
            "image": image_count,
            "video": video_count,
            "tts": tts_count,
            "synthesis": synth_count,
        }
    )


# ============== 预算管理API ==============

@router.post("/budget")
async def set_budget(
    request: BudgetSettingRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """设置预算提醒"""
    # 简单的内存存储，实际应存储到数据库
    # 这里使用 JSON 文件或数据库表存储预算设置
    # 为简化，直接返回设置值
    monthly_limit = request.monthly_limit
    warning_threshold = request.warning_threshold

    # 计算当月使用量
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 总成本
    total_result = await db.execute(
        select(func.sum(LLMUsageLog.cost))
        .where(
            LLMUsageLog.user_id == user_id,
            LLMUsageLog.created_at >= month_start
        )
    )
    llm_cost = total_result.scalar() or 0.0

    # 加上其他成本
    image_result = await db.execute(
        select(func.sum(ImageJob.cost))
        .where(
            ImageJob.user_id == user_id,
            ImageJob.created_at >= month_start,
            ImageJob.status == "succeeded"
        )
    )
    image_cost = float(image_result.scalar() or 0)

    current_usage = llm_cost + image_cost
    usage_percentage = (current_usage / monthly_limit * 100) if monthly_limit > 0 else 0
    is_warning = usage_percentage >= (warning_threshold * 100)

    return BudgetSettingResponse(
        monthly_limit=monthly_limit,
        warning_threshold=warning_threshold,
        current_usage=round(current_usage, 4),
        usage_percentage=round(usage_percentage, 2),
        is_warning=is_warning,
    )


@router.get("/budget")
async def get_budget(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取预算状态"""
    # 模拟数据，实际应从数据库读取
    return {
        "monthly_limit": 100.0,
        "warning_threshold": 0.8,
        "current_usage": 0.0,
        "usage_percentage": 0.0,
        "is_warning": False,
    }


# ============== 价格表API ==============

@router.get("/pricing")
async def get_pricing():
    """获取当前价格表"""
    return {
        "pricing": PRICING,
        "currency": "CNY",
        "unit": "元",
        "last_updated": datetime.now().isoformat(),
    }
