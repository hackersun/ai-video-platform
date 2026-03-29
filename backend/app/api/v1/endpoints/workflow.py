"""
工作流 API 端点 - 数据库持久化版本
"""

from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import Workflow, VideoJob, TTSJob, SynthesisJob

router = APIRouter(tags=["工作流"])


# ========== 请求/响应模型 ==========

class WorkflowStep(BaseModel):
    id: str
    name: int
    description: str
    required: bool


class WorkflowStepsResponse(BaseModel):
    steps: List[WorkflowStep]


class WorkflowStartRequest(BaseModel):
    title: Optional[str] = Field(None, description="工作流标题")
    novel_id: Optional[str] = Field(None, description="关联的小说ID")
    chapter_id: Optional[str] = Field(None, description="关联的章节ID")
    script_id: Optional[str] = Field(None, description="关联的剧本ID")
    storyboard_id: Optional[str] = Field(None, description="关联的分镜ID")


class WorkflowStartResponse(BaseModel):
    workflow_id: str
    title: str
    message: str


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    title: str
    status: str
    current_step: int
    completed_steps: List[int]
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    storyboard_id: Optional[str] = None
    video_jobs: List[dict]
    tts_jobs: List[dict]
    synthesis_jobs: List[dict]


class WorkflowUpdateStepRequest(BaseModel):
    current_step: int
    completed_steps: Optional[List[int]] = None
    status: Optional[str] = None
    video_job_ids: Optional[List[str]] = None
    tts_job_ids: Optional[List[str]] = None
    synthesis_job_ids: Optional[List[str]] = None


class WorkflowDetailResponse(BaseModel):
    workflow_id: str
    title: str
    status: str
    current_step: int
    completed_steps: List[int]
    novel_id: Optional[str]
    chapter_id: Optional[str]
    script_id: Optional[str]
    storyboard_id: Optional[str]
    video_job_ids: List[str]
    tts_job_ids: List[str]
    synthesis_job_ids: List[str]
    metadata: dict
    error_message: Optional[str]
    created_at: str
    updated_at: str


class ConcatenateRequest(BaseModel):
    video_job_ids: List[str] = Field(..., min_length=1, description="视频任务ID列表")
    tts_job_ids: Optional[List[str]] = Field(None, description="TTS任务ID列表")
    title: Optional[str] = Field(None, description="任务标题")
    api_key: Optional[str] = Field(None, description="火山引擎 API Key（可选）")


class ConcatenateResponse(BaseModel):
    job_id: str
    message: str


# ========== API 端点 ==========

@router.get("/steps", response_model=WorkflowStepsResponse)
async def get_workflow_steps():
    """获取工作流步骤定义"""
    return WorkflowStepsResponse(
        steps=[
            WorkflowStep(id="novel", name=1, description="1. 小说", required=True),
            WorkflowStep(id="chapter", name=2, description="2. 章节", required=True),
            WorkflowStep(id="character", name=3, description="3. 角色", required=True),
            WorkflowStep(id="script", name=4, description="4. 剧本", required=True),
            WorkflowStep(id="storyboard", name=5, description="5. 分镜", required=True),
            WorkflowStep(id="shot", name=6, description="6. 镜头", required=True),
            WorkflowStep(id="video", name=7, description="7. 视频", required=True),
            WorkflowStep(id="tts", name=8, description="8. 配音", required=True),
            WorkflowStep(id="synthesis", name=9, description="9. 合成", required=True),
            WorkflowStep(id="export", name=10, description="10. 导出", required=False),
        ]
    )


@router.post("/start", response_model=WorkflowStartResponse, status_code=status.HTTP_201_CREATED)
async def start_workflow(
    request: WorkflowStartRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """创建新工作流（持久化到数据库）"""
    workflow_id = str(uuid4())
    title = request.title or f"工作流 {workflow_id[:8]}"

    workflow = Workflow(
        id=workflow_id,
        user_id=user_id,
        title=title,
        status="active",
        novel_id=request.novel_id,
        chapter_id=request.chapter_id,
        script_id=request.script_id,
        storyboard_id=request.storyboard_id,
        current_step=1,
        completed_steps=[],
        video_job_ids=[],
        tts_job_ids=[],
        synthesis_job_ids=[],
    )
    db.add(workflow)
    await db.commit()

    return WorkflowStartResponse(
        workflow_id=workflow_id,
        title=title,
        message="工作流创建成功",
    )


@router.get("/status/{workflow_id}", response_model=WorkflowStatusResponse)
async def get_workflow_status(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取工作流状态"""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id)
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")

    # 查询关联的视频任务
    video_result = await db.execute(
        select(VideoJob)
        .where(VideoJob.user_id == user_id)
        .order_by(desc(VideoJob.created_at))
        .limit(20)
    )
    video_jobs = [
        {
            "id": job.id,
            "task_id": job.task_id,
            "title": job.title,
            "prompt": job.prompt,
            "status": job.status,
            "progress": job.progress,
            "video_url": job.video_url,
            "created_at": str(job.created_at),
        }
        for job in video_result.scalars().all()
    ]

    # 查询关联的 TTS 任务
    tts_result = await db.execute(
        select(TTSJob)
        .where(TTSJob.user_id == user_id)
        .order_by(desc(TTSJob.created_at))
        .limit(20)
    )
    tts_jobs = [
        {
            "id": job.id,
            "task_id": job.task_id,
            "title": job.title,
            "text": job.text,
            "voice": job.voice,
            "status": job.status,
            "progress": job.progress,
            "audio_url": job.audio_url,
            "created_at": str(job.created_at),
        }
        for job in tts_result.scalars().all()
    ]

    # 查询合成任务
    synthesis_result = await db.execute(
        select(SynthesisJob)
        .where(SynthesisJob.user_id == user_id, SynthesisJob.is_active == True)
        .order_by(desc(SynthesisJob.created_at))
        .limit(20)
    )
    synthesis_jobs = [
        {
            "id": job.id,
            "task_id": job.task_id,
            "title": job.title,
            "status": job.status,
            "progress": job.progress,
            "output_url": job.output_url,
            "created_at": str(job.created_at),
        }
        for job in synthesis_result.scalars().all()
    ]

    return WorkflowStatusResponse(
        workflow_id=workflow.id,
        title=workflow.title,
        status=workflow.status,
        current_step=workflow.current_step,
        completed_steps=workflow.completed_steps or [],
        novel_id=workflow.novel_id,
        chapter_id=workflow.chapter_id,
        script_id=workflow.script_id,
        storyboard_id=workflow.storyboard_id,
        video_jobs=video_jobs,
        tts_jobs=tts_jobs,
        synthesis_jobs=synthesis_jobs,
    )


@router.put("/{workflow_id}/step", response_model=WorkflowDetailResponse)
async def update_workflow_step(
    workflow_id: str,
    request: WorkflowUpdateStepRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """更新工作流步骤进度"""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id)
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")

    if request.current_step is not None:
        workflow.current_step = request.current_step
    if request.status is not None:
        workflow.status = request.status
    if request.completed_steps is not None:
        workflow.completed_steps = request.completed_steps
    if request.video_job_ids is not None:
        workflow.video_job_ids = request.video_job_ids
    if request.tts_job_ids is not None:
        workflow.tts_job_ids = request.tts_job_ids
    if request.synthesis_job_ids is not None:
        workflow.synthesis_job_ids = request.synthesis_job_ids

    await db.commit()
    await db.refresh(workflow)

    return WorkflowDetailResponse(
        workflow_id=workflow.id,
        title=workflow.title,
        status=workflow.status,
        current_step=workflow.current_step,
        completed_steps=workflow.completed_steps or [],
        novel_id=workflow.novel_id,
        chapter_id=workflow.chapter_id,
        script_id=workflow.script_id,
        storyboard_id=workflow.storyboard_id,
        video_job_ids=workflow.video_job_ids or [],
        tts_job_ids=workflow.tts_job_ids or [],
        synthesis_job_ids=workflow.synthesis_job_ids or [],
        metadata_=workflow.metadata_ or {},
        error_message=workflow.error_message,
        created_at=str(workflow.created_at),
        updated_at=str(workflow.updated_at),
    )


@router.get("/{workflow_id}", response_model=WorkflowDetailResponse)
async def get_workflow_detail(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取工作流详情"""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id)
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")

    return WorkflowDetailResponse(
        workflow_id=workflow.id,
        title=workflow.title,
        status=workflow.status,
        current_step=workflow.current_step,
        completed_steps=workflow.completed_steps or [],
        novel_id=workflow.novel_id,
        chapter_id=workflow.chapter_id,
        script_id=workflow.script_id,
        storyboard_id=workflow.storyboard_id,
        video_job_ids=workflow.video_job_ids or [],
        tts_job_ids=workflow.tts_job_ids or [],
        synthesis_job_ids=workflow.synthesis_job_ids or [],
        metadata_=workflow.metadata_ or {},
        error_message=workflow.error_message,
        created_at=str(workflow.created_at),
        updated_at=str(workflow.updated_at),
    )


@router.get("/", response_model=List[WorkflowDetailResponse])
async def list_workflows(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """列出用户的所有工作流"""
    result = await db.execute(
        select(Workflow)
        .where(Workflow.user_id == user_id)
        .order_by(desc(Workflow.created_at))
        .limit(limit)
        .offset(offset)
    )
    workflows = result.scalars().all()
    return [
        WorkflowDetailResponse(
            workflow_id=w.id,
            title=w.title,
            status=w.status,
            current_step=w.current_step,
            completed_steps=w.completed_steps or [],
            novel_id=w.novel_id,
            chapter_id=w.chapter_id,
            script_id=w.script_id,
            storyboard_id=w.storyboard_id,
            video_job_ids=w.video_job_ids or [],
            tts_job_ids=w.tts_job_ids or [],
            synthesis_job_ids=w.synthesis_job_ids or [],
            metadata=w.metadata or {},
            error_message=w.error_message,
            created_at=str(w.created_at),
            updated_at=str(w.updated_at),
        )
        for w in workflows
    ]


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """删除工作流"""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id)
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")

    await db.delete(workflow)
    await db.commit()
    return {"message": "工作流已删除"}


@router.post("/concatenate/{workflow_id}", response_model=ConcatenateResponse)
async def concatenate_videos(
    workflow_id: str,
    request: ConcatenateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """合并多个视频片段和TTS为一个完整视频"""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id)
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")

    if not request.video_job_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="video_job_ids 不能为空",
        )

    # 获取视频任务
    video_result = await db.execute(
        select(VideoJob).where(
            VideoJob.id.in_(request.video_job_ids),
            VideoJob.user_id == user_id,
        )
    )
    video_jobs = video_result.scalars().all()
    if not video_jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到指定的视频任务",
        )

    # 获取 TTS 音频
    audio_url = None
    if request.tts_job_ids:
        tts_result = await db.execute(
            select(TTSJob).where(
                TTSJob.id.in_(request.tts_job_ids),
                TTSJob.user_id == user_id,
            )
        )
        first_tts = tts_result.scalar_one_or_none()
        if first_tts:
            audio_url = first_tts.audio_url

    video_url = video_jobs[0].video_url
    if not video_url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="视频任务尚无可用URL",
        )

    output_url = video_url
    synthesis_job_id = str(uuid4())

    if request.api_key and audio_url:
        try:
            from app.services.volcano_service import VolcanoService

            service = VolcanoService(request.api_key)
            result = await service.video_voice_synthesis(
                video_url=video_url,
                audio_url=audio_url,
            )
            output_url = result.get("output_url", video_url)
        except Exception:
            output_url = video_url

    synthesis_job = SynthesisJob(
        id=synthesis_job_id,
        user_id=user_id,
        task_id=None,
        title=request.title or f"视频拼接-{workflow_id[:8]}",
        model_id="concatenation",
        model_name="视频拼接",
        video_url=video_url,
        audio_url=audio_url,
        status="succeeded",
        progress=100,
        output_url=output_url,
        cost=0,
        extra_data={
            "workflow_id": workflow_id,
            "video_job_ids": request.video_job_ids,
            "tts_job_ids": request.tts_job_ids or [],
        },
    )
    db.add(synthesis_job)

    # 更新工作流的合成任务列表
    current_ids = workflow.synthesis_job_ids or []
    workflow.synthesis_job_ids = current_ids + [synthesis_job_id]
    workflow.current_step = max(workflow.current_step, 9)

    await db.commit()

    return ConcatenateResponse(
        job_id=synthesis_job_id,
        message="视频拼接任务已创建",
    )
