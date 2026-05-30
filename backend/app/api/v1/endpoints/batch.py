"""
批量任务 API 端点
"""
import uuid
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import BatchJob, BatchJobItem, Shot

router = APIRouter(prefix="/batch", tags=["批量任务"])


# ============== Pydantic 模型 ==============

class BatchCreateRequest(BaseModel):
    job_type: str = Field(..., description="任务类型: image, tts, video")
    title: Optional[str] = Field(None, description="任务标题")
    shot_ids: List[str] = Field(..., min_length=1, description="镜头ID列表")
    storyboard_id: Optional[str] = Field(None, description="分镜ID")
    workflow_id: Optional[str] = Field(None, description="工作流ID")
    extra_data: Optional[dict] = Field(None, description="额外参数")


class BatchJobResponse(BaseModel):
    id: str
    job_type: str
    title: Optional[str]
    status: str
    total_count: int
    pending_count: int
    running_count: int
    succeeded_count: int
    failed_count: int
    skipped_count: int
    storyboard_id: Optional[str]
    shot_ids: List[str]
    workflow_id: Optional[str]
    created_at: str
    updated_at: str


class BatchItemResponse(BaseModel):
    id: str
    batch_job_id: str
    shot_id: str
    status: str
    image_url: Optional[str]
    video_url: Optional[str]
    audio_url: Optional[str]
    image_job_id: Optional[str]
    video_job_id: Optional[str]
    tts_job_id: Optional[str]
    error_message: Optional[str]
    sort_order: int
    created_at: str
    updated_at: str


class BatchJobListResponse(BaseModel):
    total: int
    jobs: List[BatchJobResponse]


class BatchItemListResponse(BaseModel):
    total: int
    items: List[BatchItemResponse]


class BatchProgressResponse(BaseModel):
    job_id: str
    status: str
    total_count: int
    pending_count: int
    running_count: int
    succeeded_count: int
    failed_count: int
    skipped_count: int
    progress_percent: float
    message: str


# ============== 辅助函数 ==============

async def _get_batch_job(db: AsyncSession, job_id: str, user_id: str) -> BatchJob:
    result = await db.execute(
        select(BatchJob).where(BatchJob.id == job_id, BatchJob.user_id == user_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="批量任务不存在")
    return job


def _build_batch_job_response(job: BatchJob) -> BatchJobResponse:
    return BatchJobResponse(
        id=job.id,
        job_type=job.job_type,
        title=job.title,
        status=job.status,
        total_count=job.total_count,
        pending_count=job.pending_count,
        running_count=job.running_count,
        succeeded_count=job.succeeded_count,
        failed_count=job.failed_count,
        skipped_count=job.skipped_count,
        storyboard_id=job.storyboard_id,
        shot_ids=job.shot_ids or [],
        workflow_id=job.workflow_id,
        created_at=str(job.created_at),
        updated_at=str(job.updated_at),
    )


def _build_batch_item_response(item: BatchJobItem) -> BatchItemResponse:
    return BatchItemResponse(
        id=item.id,
        batch_job_id=item.batch_job_id,
        shot_id=item.shot_id,
        status=item.status,
        image_url=item.image_url,
        video_url=item.video_url,
        audio_url=item.audio_url,
        image_job_id=item.image_job_id,
        video_job_id=item.video_job_id,
        tts_job_id=item.tts_job_id,
        error_message=item.error_message,
        sort_order=item.sort_order,
        created_at=str(item.created_at),
        updated_at=str(item.updated_at),
    )


def _recalculate_batch_counts(job: BatchJob, items: List[BatchJobItem]) -> None:
    """重新计算批量任务统计"""
    job.total_count = len(items)
    job.pending_count = sum(1 for item in items if item.status == "pending")
    job.running_count = sum(1 for item in items if item.status == "running")
    job.succeeded_count = sum(1 for item in items if item.status == "succeeded")
    job.failed_count = sum(1 for item in items if item.status == "failed")
    job.skipped_count = sum(1 for item in items if item.status == "skipped")

    # 更新任务状态
    if job.failed_count == job.total_count:
        job.status = "failed"
    elif job.succeeded_count + job.skipped_count == job.total_count:
        job.status = "completed"
    elif job.running_count > 0:
        job.status = "running"
    elif job.pending_count == job.total_count:
        job.status = "pending"


# ============== API 端点 ==============

@router.post("/create", response_model=BatchJobResponse, status_code=status.HTTP_201_CREATED)
async def create_batch_job(
    request: BatchCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """创建批量任务"""
    if request.job_type not in ("image", "tts", "video"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="job_type 必须是 image, tts 或 video",
        )

    # 验证shot存在
    shot_result = await db.execute(
        select(Shot).where(
            Shot.id.in_(request.shot_ids),
            Shot.user_id == user_id,
        )
    )
    shots = shot_result.scalars().all()
    if len(shots) != len(request.shot_ids):
        found_ids = {shot.id for shot in shots}
        missing = [id for id in request.shot_ids if id not in found_ids]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"部分镜头不存在或无权访问: {missing}",
        )

    job_id = str(uuid4())
    title = request.title or f"批量生成{request.job_type} ({len(request.shot_ids)}个)"

    # 创建批量任务
    batch_job = BatchJob(
        id=job_id,
        user_id=user_id,
        job_type=request.job_type,
        title=title,
        status="pending",
        total_count=len(request.shot_ids),
        pending_count=len(request.shot_ids),
        storyboard_id=request.storyboard_id,
        shot_ids=request.shot_ids,
        workflow_id=request.workflow_id,
        extra_data=request.extra_data or {},
    )
    db.add(batch_job)

    # 创建任务项
    items = []
    for idx, shot_id in enumerate(request.shot_ids):
        item = BatchJobItem(
            id=str(uuid4()),
            batch_job_id=job_id,
            user_id=user_id,
            shot_id=shot_id,
            status="pending",
            sort_order=idx,
        )
        items.append(item)
        db.add(item)

    await db.commit()
    await db.refresh(batch_job)

    return _build_batch_job_response(batch_job)


@router.get("/list", response_model=BatchJobListResponse)
async def list_batch_jobs(
    job_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取批量任务列表"""
    query = select(BatchJob).where(BatchJob.user_id == user_id, BatchJob.is_active == True)

    if job_type:
        query = query.where(BatchJob.job_type == job_type)
    if status:
        query = query.where(BatchJob.status == status)

    query = query.order_by(BatchJob.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    jobs = result.scalars().all()

    # 获取总数
    count_query = select(BatchJob).where(BatchJob.user_id == user_id, BatchJob.is_active == True)
    if job_type:
        count_query = count_query.where(BatchJob.job_type == job_type)
    if status:
        count_query = count_query.where(BatchJob.status == status)
    total_result = await db.execute(count_query)
    total = len(total_result.scalars().all())

    return BatchJobListResponse(total=total, jobs=[_build_batch_job_response(job) for job in jobs])


@router.get("/{job_id}", response_model=BatchJobResponse)
async def get_batch_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取批量任务详情"""
    job = await _get_batch_job(db, job_id, user_id)
    return _build_batch_job_response(job)


@router.get("/{job_id}/progress", response_model=BatchProgressResponse)
async def get_batch_job_progress(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取批量任务进度"""
    job = await _get_batch_job(db, job_id, user_id)

    # 获取任务项
    items_result = await db.execute(
        select(BatchJobItem).where(
            BatchJobItem.batch_job_id == job_id,
            BatchJobItem.user_id == user_id,
        ).order_by(BatchJobItem.sort_order)
    )
    items = items_result.scalars().all()

    # 重新计算统计
    _recalculate_batch_counts(job, items)

    # 计算进度百分比
    if job.total_count > 0:
        completed = job.succeeded_count + job.failed_count + job.skipped_count
        progress_percent = (completed / job.total_count) * 100
    else:
        progress_percent = 0

    message = f"已完成 {job.succeeded_count}/{job.total_count}"
    if job.failed_count > 0:
        message += f", 失败 {job.failed_count}"
    if job.skipped_count > 0:
        message += f", 跳过 {job.skipped_count}"

    return BatchProgressResponse(
        job_id=job.id,
        status=job.status,
        total_count=job.total_count,
        pending_count=job.pending_count,
        running_count=job.running_count,
        succeeded_count=job.succeeded_count,
        failed_count=job.failed_count,
        skipped_count=job.skipped_count,
        progress_percent=round(progress_percent, 2),
        message=message,
    )


@router.get("/{job_id}/items", response_model=BatchItemListResponse)
async def get_batch_job_items(
    job_id: str,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取批量任务项列表"""
    job = await _get_batch_job(db, job_id, user_id)

    query = select(BatchJobItem).where(
        BatchJobItem.batch_job_id == job_id,
        BatchJobItem.user_id == user_id,
    ).order_by(BatchJobItem.sort_order)

    if status:
        query = query.where(BatchJobItem.status == status)

    result = await db.execute(query)
    items = result.scalars().all()

    return BatchItemListResponse(total=len(items), items=[_build_batch_item_response(item) for item in items])


@router.post("/{job_id}/start", response_model=BatchJobResponse)
async def start_batch_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """启动批量任务"""
    job = await _get_batch_job(db, job_id, user_id)

    if job.status not in ("pending", "paused"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"无法启动状态为 {job.status} 的任务",
        )

    job.status = "running"
    await db.commit()
    await db.refresh(job)

    return _build_batch_job_response(job)


@router.post("/{job_id}/pause", response_model=BatchJobResponse)
async def pause_batch_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """暂停批量任务"""
    job = await _get_batch_job(db, job_id, user_id)

    if job.status != "running":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"只能暂停运行中的任务，当前状态: {job.status}",
        )

    job.status = "paused"

    # 将pending和running的项标记为pending（暂停后可恢复）
    items_result = await db.execute(
        select(BatchJobItem).where(
            BatchJobItem.batch_job_id == job_id,
            BatchJobItem.user_id == user_id,
        ).where(BatchJobItem.status.in_(["pending", "running"]))
    )
    for item in items_result.scalars().all():
        item.status = "pending"

    await db.commit()
    await db.refresh(job)

    return _build_batch_job_response(job)


@router.post("/{job_id}/resume", response_model=BatchJobResponse)
async def resume_batch_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """恢复批量任务"""
    job = await _get_batch_job(db, job_id, user_id)

    if job.status != "paused":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"只能恢复暂停的任务，当前状态: {job.status}",
        )

    job.status = "running"
    await db.commit()
    await db.refresh(job)

    return _build_batch_job_response(job)


@router.post("/{job_id}/retry-failed", response_model=BatchJobResponse)
async def retry_failed_items(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """重试失败项"""
    job = await _get_batch_job(db, job_id, user_id)

    # 将失败的项重置为pending
    items_result = await db.execute(
        select(BatchJobItem).where(
            BatchJobItem.batch_job_id == job_id,
            BatchJobItem.user_id == user_id,
            BatchJobItem.status == "failed",
        )
    )
    items = items_result.scalars().all()

    if not items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="没有失败项需要重试",
        )

    for item in items:
        item.status = "pending"
        item.error_message = None

    job.status = "running"
    job.pending_count = job.pending_count + len(items)
    job.failed_count = 0

    await db.commit()
    await db.refresh(job)

    return _build_batch_job_response(job)


@router.post("/{job_id}/skip/{item_id}", response_model=BatchItemResponse)
async def skip_batch_item(
    job_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """跳过某项"""
    job = await _get_batch_job(db, job_id, user_id)

    # 查找任务项
    item_result = await db.execute(
        select(BatchJobItem).where(
            BatchJobItem.id == item_id,
            BatchJobItem.batch_job_id == job_id,
            BatchJobItem.user_id == user_id,
        )
    )
    item = item_result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="任务项不存在")

    if item.status not in ("pending", "running"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"只能跳过 pending/running 状态的项目，当前: {item.status}",
        )

    item.status = "skipped"
    job.skipped_count = job.skipped_count + 1

    await db.commit()
    await db.refresh(item)

    return _build_batch_item_response(item)


@router.put("/{job_id}/items/{item_id}", response_model=BatchItemResponse)
async def update_batch_item(
    job_id: str,
    item_id: str,
    status: Optional[str] = None,
    image_url: Optional[str] = None,
    video_url: Optional[str] = None,
    audio_url: Optional[str] = None,
    image_job_id: Optional[str] = None,
    video_job_id: Optional[str] = None,
    tts_job_id: Optional[str] = None,
    error_message: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """更新任务项状态"""
    job = await _get_batch_job(db, job_id, user_id)

    item_result = await db.execute(
        select(BatchJobItem).where(
            BatchJobItem.id == item_id,
            BatchJobItem.batch_job_id == job_id,
            BatchJobItem.user_id == user_id,
        )
    )
    item = item_result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="任务项不存在")

    old_status = item.status

    if status:
        item.status = status
    if image_url is not None:
        item.image_url = image_url
    if video_url is not None:
        item.video_url = video_url
    if audio_url is not None:
        item.audio_url = audio_url
    if image_job_id is not None:
        item.image_job_id = image_job_id
    if video_job_id is not None:
        item.video_job_id = video_job_id
    if tts_job_id is not None:
        item.tts_job_id = tts_job_id
    if error_message is not None:
        item.error_message = error_message

    # 更新计数
    if old_status != item.status:
        # 减少旧状态的计数
        if old_status == "pending":
            job.pending_count = max(0, job.pending_count - 1)
        elif old_status == "running":
            job.running_count = max(0, job.running_count - 1)
        elif old_status == "succeeded":
            job.succeeded_count = max(0, job.succeeded_count - 1)
        elif old_status == "failed":
            job.failed_count = max(0, job.failed_count - 1)
        elif old_status == "skipped":
            job.skipped_count = max(0, job.skipped_count - 1)

        # 增加新状态的计数
        if item.status == "pending":
            job.pending_count += 1
        elif item.status == "running":
            job.running_count += 1
        elif item.status == "succeeded":
            job.succeeded_count += 1
        elif item.status == "failed":
            job.failed_count += 1
        elif item.status == "skipped":
            job.skipped_count += 1

    # 检查是否全部完成
    completed = job.succeeded_count + job.failed_count + job.skipped_count
    if completed == job.total_count:
        if job.failed_count == job.total_count:
            job.status = "failed"
        else:
            job.status = "completed"

    await db.commit()
    await db.refresh(item)

    return _build_batch_item_response(item)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_batch_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """删除批量任务"""
    job = await _get_batch_job(db, job_id, user_id)

    # 软删除
    job.is_active = False

    # 同时删除所有关联项
    items_result = await db.execute(
        select(BatchJobItem).where(
            BatchJobItem.batch_job_id == job_id,
            BatchJobItem.user_id == user_id,
        )
    )
    for item in items_result.scalars().all():
        item.status = "cancelled"

    await db.commit()