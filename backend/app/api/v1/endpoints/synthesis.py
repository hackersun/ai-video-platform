"""
音视频合成 API 端点
支持将视频与音频合并
"""

from app.core.time_utils import utc_now
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel, Field, HttpUrl

from app.core.database import get_db
from app.core.dev_generation import dev_synthesis_url, is_dev_mode
from app.core.permissions import require_project_role
from app.core.security import get_current_user_id
from app.models.publication import Publication
from app.models.synthesis_job import SynthesisJob
from app.models.tts_job import TTSJob
from app.models.video_job import VideoJob
from app.services.media_delivery import resolve_provider_media_url
from app.services.publication_readiness import evaluate_publication_readiness

router = APIRouter(tags=["音视频合成"])


# ============== 请求/响应模型 ==============

class SynthesisCreateRequest(BaseModel):
    """创建合成任务请求"""
    video_job_id: Optional[str] = Field(None, description="视频任务ID")
    tts_job_id: Optional[str] = Field(None, description="TTS任务ID")
    video_url: Optional[str] = Field(None, description="视频URL")
    audio_url: Optional[str] = Field(None, description="音频URL")
    title: Optional[str] = Field(None, description="作品标题")
    project_id: Optional[str] = Field(None, description="关联的项目ID")
    workflow_id: Optional[str] = Field(None, description="关联的工作流ID")
    api_key: Optional[str] = Field(None, description="兼容旧字段：直接传入API Key")


class SynthesisStatusUpdate(BaseModel):
    """更新合成状态"""
    status: str = Field(..., description="状态: pending, running, succeeded, failed")
    progress: Optional[int] = Field(None, ge=0, le=100, description="进度百分比")
    output_url: Optional[str] = Field(None, description="输出URL")
    error_message: Optional[str] = Field(None, description="错误信息")


class SynthesisJobResponse(BaseModel):
    """合成任务响应"""
    id: str
    job_id: Optional[str] = None
    user_id: str
    task_id: Optional[str] = None
    project_id: Optional[str] = None
    workflow_id: Optional[str] = None
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    storyboard_id: Optional[str] = None
    shot_id: Optional[str] = None
    video_job_id: Optional[str] = None
    tts_job_id: Optional[str] = None
    title: Optional[str] = None
    model_id: Optional[str] = None
    model_name: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    status: str
    progress: int
    output_url: Optional[str] = None
    cover_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    manifest_url: Optional[str] = None
    preview_url: Optional[str] = None
    srt_url: Optional[str] = None
    timeline_url: Optional[str] = None
    render_manifest_url: Optional[str] = None
    render_status: Optional[str] = None
    render_backend: Optional[str] = None
    is_publishable: bool = False
    output_kind: str = "missing_final_video"
    publication_blockers: List[Dict[str, Any]] = Field(default_factory=list)
    segment_count: Optional[int] = None
    cost: Optional[int] = 0
    error_message: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class PublicationCreateRequest(BaseModel):
    """创建本地导出/发布记录请求"""
    synthesis_job_id: Optional[str] = Field(None, description="合成任务ID")
    project_id: Optional[str] = Field(None, description="项目ID")
    title: Optional[str] = Field(None, max_length=200, description="导出标题")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="导出元数据")


class PublicationUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=200, description="发布标题")
    status: Optional[str] = Field(None, description="发布状态")
    visibility: Optional[str] = Field(None, description="可见性")
    tags: Optional[List[str]] = Field(None, description="标签")
    description: Optional[str] = Field(None, description="描述")
    format: Optional[str] = Field(None, description="格式")
    resolution: Optional[str] = Field(None, description="分辨率")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class SubtitleSegmentInput(BaseModel):
    """字幕片段输入"""
    text: str
    start_time: float
    end_time: float
    style: Optional[Dict[str, Any]] = None


class SynthesisExecuteRequest(BaseModel):
    """执行真实合成请求"""
    video_urls: List[str] = Field(..., description="视频URL列表")
    audio_urls: Optional[List[str]] = Field(None, description="音频URL列表")
    subtitles: Optional[List[SubtitleSegmentInput]] = Field(None, description="字幕片段")
    title: Optional[str] = Field(None, max_length=200, description="作品标题")
    output_format: str = Field("mp4", description="输出格式")
    quality: str = Field("high", description="质量: low, medium, high")
    project_id: Optional[str] = Field(None, description="项目ID")
    workflow_id: Optional[str] = Field(None, description="工作流ID")


class SynthesisExecuteResponse(BaseModel):
    """执行合成响应"""
    job_id: str
    status: str
    video_url: Optional[str] = None
    cover_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None


class PublicationResponse(BaseModel):
    """发布响应"""
    id: str
    user_id: str
    project_id: Optional[str] = None
    synthesis_job_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    status: str
    visibility: str
    video_url: Optional[str] = None
    cover_url: Optional[str] = None
    format: str = "mp4"
    resolution: str = "1080p"
    duration_seconds: Optional[float] = None
    tags: List[str] = Field(default_factory=list)
    view_count: int = 0
    like_count: int = 0
    export_url: Optional[str] = None
    provider: str = "local"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: Optional[datetime] = None


async def get_publication_or_404(db: AsyncSession, publication_id: str, user_id: str) -> Publication:
    result = await db.execute(
        select(Publication).where(Publication.id == publication_id, Publication.user_id == user_id)
    )
    publication = result.scalar_one_or_none()
    if not publication:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="发布记录不存在")
    return publication


def build_synthesis_response(job: SynthesisJob) -> SynthesisJobResponse:
    """Build a stable API response from the current SynthesisJob schema."""
    extra_data = job.extra_data or {}
    render_artifacts = extra_data.get("render_artifacts") if isinstance(extra_data.get("render_artifacts"), dict) else {}
    publication_readiness = evaluate_publication_readiness(job.output_url, extra_data)
    return SynthesisJobResponse(
        id=job.id,
        job_id=job.id,
        user_id=job.user_id,
        task_id=job.task_id,
        project_id=job.project_id or extra_data.get("project_id"),
        workflow_id=job.workflow_id or extra_data.get("workflow_id"),
        novel_id=_first_lineage_value(extra_data, "novel_id"),
        chapter_id=_first_lineage_value(extra_data, "chapter_id"),
        script_id=_first_lineage_value(extra_data, "script_id"),
        storyboard_id=_first_lineage_value(extra_data, "storyboard_id"),
        shot_id=_first_lineage_value(extra_data, "shot_id"),
        video_job_id=extra_data.get("video_job_id"),
        tts_job_id=extra_data.get("tts_job_id"),
        title=job.title,
        model_id=job.model_id,
        model_name=job.model_name,
        video_url=job.video_url,
        audio_url=job.audio_url,
        status=job.status,
        progress=job.progress or 0,
        output_url=job.output_url,
        cover_url=job.cover_url,
        duration_seconds=job.duration_seconds,
        manifest_url=extra_data.get("manifest_url") or render_artifacts.get("source_manifest_url"),
        preview_url=render_artifacts.get("preview_url"),
        srt_url=render_artifacts.get("srt_url"),
        timeline_url=render_artifacts.get("timeline_url"),
        render_manifest_url=render_artifacts.get("render_manifest_url"),
        render_status=extra_data.get("render_status"),
        render_backend=extra_data.get("render_backend"),
        is_publishable=publication_readiness["is_publishable"],
        output_kind=publication_readiness["output_kind"],
        publication_blockers=publication_readiness["publication_blockers"],
        segment_count=extra_data.get("segment_count"),
        cost=job.cost or 0,
        error_message=job.error_message,
        extra_data=extra_data,
        is_active=job.is_active if job.is_active is not None else True,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _lineage_values(extra_data: Dict[str, Any], key: str) -> set[str]:
    """Return lineage values stored at top level, lineage, or segment lineage."""
    values: set[str] = set()
    top_value = extra_data.get(key)
    if top_value:
        values.add(str(top_value))

    lineage = extra_data.get("lineage")
    if isinstance(lineage, dict) and lineage.get(key):
        values.add(str(lineage[key]))

    segments = extra_data.get("segments")
    if isinstance(segments, list):
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            if segment.get(key):
                values.add(str(segment[key]))
            segment_lineage = segment.get("lineage")
            if isinstance(segment_lineage, dict) and segment_lineage.get(key):
                values.add(str(segment_lineage[key]))

    return values


def _first_lineage_value(extra_data: Dict[str, Any], key: str) -> Optional[str]:
    values = _lineage_values(extra_data, key)
    return sorted(values)[0] if values else None


def _job_generation_preflight(job: Any) -> Optional[Dict[str, Any]]:
    extra = job.extra_data if isinstance(job.extra_data, dict) else {}
    preflight = extra.get("generation_preflight")
    return dict(preflight) if isinstance(preflight, dict) else None


def _source_preflight_entry(source_type: str, job: Any) -> Optional[Dict[str, Any]]:
    preflight = _job_generation_preflight(job)
    if preflight is None:
        return None
    return {
        "source_type": source_type,
        "job_id": job.id,
        "task_id": getattr(job, "task_id", None),
        "preflight": preflight,
    }


def _aggregate_source_preflight(sources: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not sources:
        return None
    issues: List[Dict[str, Any]] = []
    blocking_issue_count = 0
    ready = True
    for source in sources:
        preflight = source.get("preflight") if isinstance(source, dict) else None
        if not isinstance(preflight, dict):
            continue
        if preflight.get("ready") is not True:
            ready = False
        blocking_issue_count += int(preflight.get("blocking_issue_count") or 0)
        for issue in preflight.get("issues") or []:
            if isinstance(issue, dict):
                issues.append({
                    **issue,
                    "source_type": source.get("source_type"),
                    "job_id": source.get("job_id"),
                })
    return {
        "ready": ready and blocking_issue_count == 0,
        "blocking_issue_count": blocking_issue_count,
        "issues": issues,
        "sources": sources,
    }


def _synthesis_job_matches_filters(
    job: SynthesisJob,
    *,
    status_filter: Optional[str],
    render_status: Optional[str],
    lineage_filters: Dict[str, Optional[str]],
) -> bool:
    if status_filter and job.status != status_filter:
        return False

    extra_data = job.extra_data or {}
    if render_status and extra_data.get("render_status") != render_status:
        return False

    for key, expected in lineage_filters.items():
        if expected and str(expected) not in _lineage_values(extra_data, key):
            return False

    return True


def build_publication_response(publication: Publication) -> PublicationResponse:
    return PublicationResponse(
        id=publication.id,
        user_id=publication.user_id,
        project_id=publication.project_id,
        synthesis_job_id=publication.synthesis_job_id,
        title=publication.title,
        description=publication.description,
        status=publication.status,
        visibility=publication.visibility or "private",
        video_url=publication.video_url,
        cover_url=publication.cover_url,
        format=publication.format or "mp4",
        resolution=publication.resolution or "1080p",
        duration_seconds=publication.duration_seconds,
        tags=publication.tags or [],
        view_count=publication.view_count or 0,
        like_count=publication.like_count or 0,
        export_url=publication.export_url,
        provider=publication.provider,
        metadata=publication.publication_metadata or {},
        created_at=publication.created_at,
        updated_at=publication.updated_at,
    )


def write_local_export_artifact(export_id: str, payload: Dict[str, Any]) -> tuple[Path, str]:
    export_dir = Path(__file__).resolve().parents[4] / "static" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = export_dir / f"{export_id}.json"
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    return artifact_path, f"/static/exports/{artifact_path.name}"


def _publication_delivery_media_type(key: str) -> str:
    if key == "video_url":
        return "video"
    if key == "srt_url":
        return "subtitle"
    return "manifest"


def _publication_provider_from_delivery(current_provider: str, delivery: Dict[str, Any]) -> str:
    if delivery.get("delivery_method") == "qiniu_object_upload":
        return "qiniu"
    return current_provider


async def _resolve_publication_delivery(
    db: AsyncSession,
    user_id: str,
    media_url: Optional[str],
    *,
    media_type: str,
) -> Dict[str, Any]:
    if not media_url:
        return {
            "source_url": media_url,
            "provider_url": None,
            "delivery_method": None,
            "omitted_reason": None,
        }
    try:
        return await resolve_provider_media_url(db, user_id, media_url, media_type=media_type)
    except Exception as exc:
        return {
            "source_url": media_url,
            "provider_url": None,
            "delivery_method": None,
            "omitted_reason": str(exc) or "对象存储交付失败，保留本地发布产物",
        }


async def _apply_publication_storage_delivery(
    db: AsyncSession,
    user_id: str,
    artifact_payload: Dict[str, Any],
) -> str:
    provider = "local"
    storage_delivery: Dict[str, Any] = {}
    render_artifacts = (
        artifact_payload.get("render_artifacts")
        if isinstance(artifact_payload.get("render_artifacts"), dict)
        else {}
    )
    delivery_targets: Dict[str, Optional[str]] = {
        "video_url": artifact_payload.get("video_url"),
        "srt_url": artifact_payload.get("srt_url") or render_artifacts.get("srt_url"),
        "timeline_url": artifact_payload.get("timeline_url") or render_artifacts.get("timeline_url"),
        "render_manifest_url": artifact_payload.get("render_manifest_url") or render_artifacts.get("render_manifest_url"),
        "source_manifest_url": artifact_payload.get("source_manifest_url") or render_artifacts.get("source_manifest_url"),
    }
    for key, source_url in delivery_targets.items():
        delivery = await _resolve_publication_delivery(
            db,
            user_id,
            source_url,
            media_type=_publication_delivery_media_type(key),
        )
        storage_delivery[key] = delivery
        provider_url = delivery.get("provider_url")
        if provider_url:
            if key == "video_url":
                artifact_payload["video_url"] = provider_url
            else:
                artifact_payload[key] = provider_url
                render_artifacts[key] = provider_url
            provider = _publication_provider_from_delivery(provider, delivery)
    if render_artifacts:
        artifact_payload["render_artifacts"] = render_artifacts
    artifact_payload["storage_delivery"] = storage_delivery
    artifact_payload["provider"] = provider
    return provider


async def _apply_export_artifact_storage_delivery(
    db: AsyncSession,
    user_id: str,
    artifact_payload: Dict[str, Any],
    *,
    local_export_url: str,
    current_provider: str,
) -> tuple[str, str]:
    delivery = await _resolve_publication_delivery(
        db,
        user_id,
        local_export_url,
        media_type="manifest",
    )
    storage_delivery = artifact_payload.setdefault("storage_delivery", {})
    storage_delivery["export_url"] = delivery
    artifact_payload["local_export_url"] = local_export_url
    provider_url = delivery.get("provider_url")
    provider = _publication_provider_from_delivery(current_provider, delivery)
    return provider, provider_url or local_export_url


def _raise_publication_not_ready(readiness: Dict[str, Any]) -> None:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={
            "code": "publication_not_ready",
            "message": "最终成片尚未准备好，无法创建发布导出",
            "render_status": readiness.get("render_status"),
            "output_kind": readiness.get("output_kind"),
            "issues": readiness.get("publication_blockers") or [],
            "action": readiness.get("action") or "render_final_video",
        },
    )


def _can_export_preview_package(readiness: Dict[str, Any], extra_data: Dict[str, Any], metadata: Dict[str, Any]) -> bool:
    render_artifacts = extra_data.get("render_artifacts") if isinstance(extra_data.get("render_artifacts"), dict) else {}
    return (
        bool(metadata.get("allow_preview_export"))
        and readiness.get("output_kind") == "preview_package"
        and extra_data.get("render_backend") == "local_artifact_package"
        and extra_data.get("render_status") == "rendered"
        and bool(render_artifacts.get("preview_url"))
    )


async def resolve_media_urls(
    request: SynthesisCreateRequest,
    db: AsyncSession,
    user_id: str,
) -> tuple[str, Optional[str], Dict[str, Any]]:
    """Resolve job IDs to media URLs while still allowing direct URL input."""
    video_url = request.video_url
    audio_url = request.audio_url
    extra_data: Dict[str, Any] = {}
    source_preflights: List[Dict[str, Any]] = []

    if request.video_job_id:
        extra_data["video_job_id"] = request.video_job_id
        result = await db.execute(
            select(VideoJob).where(VideoJob.id == request.video_job_id, VideoJob.user_id == user_id)
        )
        video_job = result.scalar_one_or_none()
        if not video_job:
            if not video_url:
                raise HTTPException(status_code=404, detail="视频任务不存在")
        else:
            if not video_url:
                video_url = video_job.video_url
            extra_data["project_id"] = video_job.project_id
            extra_data["workflow_id"] = video_job.workflow_id
            extra_data["video_task_id"] = video_job.task_id
            source_entry = _source_preflight_entry("video", video_job)
            if source_entry:
                source_preflights.append(source_entry)

    if request.tts_job_id:
        extra_data["tts_job_id"] = request.tts_job_id
        result = await db.execute(
            select(TTSJob).where(TTSJob.id == request.tts_job_id, TTSJob.user_id == user_id)
        )
        tts_job = result.scalar_one_or_none()
        if not tts_job:
            if not audio_url:
                raise HTTPException(status_code=404, detail="TTS任务不存在")
        else:
            if not audio_url:
                audio_url = tts_job.audio_url
            extra_data["project_id"] = extra_data.get("project_id") or tts_job.project_id
            extra_data["workflow_id"] = extra_data.get("workflow_id") or tts_job.workflow_id
            extra_data["tts_task_id"] = tts_job.task_id
            source_entry = _source_preflight_entry("tts", tts_job)
            if source_entry:
                source_preflights.append(source_entry)

    if request.project_id:
        extra_data["project_id"] = request.project_id
    if request.workflow_id:
        extra_data["workflow_id"] = request.workflow_id
    source_preflight = _aggregate_source_preflight(source_preflights)
    if source_preflight:
        extra_data["generation_preflight"] = source_preflight

    if not video_url:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="请选择已有视频任务或提供 video_url")

    return video_url, audio_url, extra_data


def validate_legacy_generate_request(request: SynthesisCreateRequest) -> None:
    """Validate direct synthesis calls that execute immediately."""
    if request.api_key is None or not request.api_key.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="api_key 不能为空")
    if not request.video_url:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="video_url 不能为空")
    if not request.audio_url:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="audio_url 不能为空")
    try:
        HttpUrl(request.video_url)
        HttpUrl(request.audio_url)
    except Exception:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="URL 格式不正确")


# ============== API 端点 ==============

@router.post("/create", response_model=SynthesisJobResponse)
async def create_synthesis(
    request: SynthesisCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建合成任务。

    当前阶段先创建可追踪的合成记录；真正的转码/混音导出后续接入任务执行器。
    """
    job_id = str(uuid4())
    video_url, audio_url, extra_data = await resolve_media_urls(request, db, user_id)
    project_id = request.project_id or extra_data.get("project_id")
    if project_id:
        await require_project_role(db, project_id, user_id, "editor")
    
    dev_complete = is_dev_mode()
    job = SynthesisJob(
        id=job_id,
        user_id=user_id,
        project_id=project_id,
        workflow_id=request.workflow_id or extra_data.get("workflow_id"),
        title=request.title or "音视频合成",
        model_id="local-synthesis",
        model_name="DEV_MODE 本地合成" if dev_complete else "本地合成占位",
        video_url=video_url,
        audio_url=audio_url,
        status="succeeded" if dev_complete else "pending",
        progress=100 if dev_complete else 0,
        output_url=dev_synthesis_url(job_id) if dev_complete else None,
        extra_data=extra_data,
    )
    
    db.add(job)
    if job.workflow_id:
        from app.models import Workflow

        workflow_result = await db.execute(
            select(Workflow).where(Workflow.id == job.workflow_id, Workflow.user_id == user_id)
        )
        workflow = workflow_result.scalar_one_or_none()
        if workflow:
            workflow.synthesis_job_ids = list(dict.fromkeys((workflow.synthesis_job_ids or []) + [job.id]))
    await db.commit()
    await db.refresh(job)
    
    return build_synthesis_response(job)


@router.post("/generate", response_model=SynthesisJobResponse)
async def generate_synthesis(
    request: SynthesisCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """兼容旧接口：直接执行一次音视频合成并记录任务。"""
    validate_legacy_generate_request(request)
    job_id = str(uuid4())
    video_url, audio_url, extra_data = await resolve_media_urls(request, db, user_id)
    project_id = request.project_id or extra_data.get("project_id")
    if project_id:
        await require_project_role(db, project_id, user_id, "editor")

    try:
        from app.services.volcano_service import VolcanoService

        service = VolcanoService(request.api_key)
        result = await service.video_voice_synthesis(video_url=video_url, audio_url=audio_url)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"音视频合成失败: {str(e)}")

    job = SynthesisJob(
        id=job_id,
        user_id=user_id,
        task_id=result.get("task_id"),
        project_id=project_id,
        workflow_id=request.workflow_id or extra_data.get("workflow_id"),
        title=request.title or "音视频合成",
        model_id=result.get("model", "volcano-synthesis"),
        model_name="volcano-synthesis",
        video_url=video_url,
        audio_url=audio_url,
        status=result.get("status", "succeeded"),
        progress=100,
        output_url=result.get("output_url", video_url),
        duration_seconds=result.get("duration"),
        extra_data=extra_data,
    )
    db.add(job)
    if job.workflow_id:
        from app.models import Workflow

        workflow_result = await db.execute(
            select(Workflow).where(Workflow.id == job.workflow_id, Workflow.user_id == user_id)
        )
        workflow = workflow_result.scalar_one_or_none()
        if workflow:
            workflow.synthesis_job_ids = list(dict.fromkeys((workflow.synthesis_job_ids or []) + [job.id]))
    await db.commit()
    await db.refresh(job)
    return build_synthesis_response(job)


@router.post("/publish", response_model=PublicationResponse, status_code=status.HTTP_201_CREATED)
async def publish_export(
    request: PublicationCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """创建本地导出记录。

    DEV_MODE/local 模式下生成可下载的静态 JSON artifact，不声明云端发布。
    """
    if not request.synthesis_job_id and not request.metadata:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="请提供 synthesis_job_id 或 metadata",
        )

    synthesis_job: Optional[SynthesisJob] = None
    if request.synthesis_job_id:
        result = await db.execute(
            select(SynthesisJob).where(
                SynthesisJob.id == request.synthesis_job_id,
                SynthesisJob.user_id == user_id,
            )
        )
        synthesis_job = result.scalar_one_or_none()
        if not synthesis_job:
            raise HTTPException(status_code=404, detail="合成任务不存在")

    project_id = request.project_id or (synthesis_job.project_id if synthesis_job else None)
    if project_id:
        await require_project_role(db, project_id, user_id, "viewer")

    export_id = str(uuid4())
    title = request.title or (synthesis_job.title if synthesis_job else None) or "本地导出"
    metadata = dict(request.metadata or {})
    job_extra_data = synthesis_job.extra_data if synthesis_job and isinstance(synthesis_job.extra_data, dict) else {}
    render_artifacts = (
        job_extra_data.get("render_artifacts")
        if isinstance(job_extra_data.get("render_artifacts"), dict)
        else {}
    )
    playback_video_url = synthesis_job.output_url if synthesis_job else metadata.get("source_output_url")
    if synthesis_job and not playback_video_url:
        _raise_publication_not_ready(evaluate_publication_readiness(playback_video_url, job_extra_data))
    preview_export = False
    readiness: Optional[Dict[str, Any]] = None
    if synthesis_job:
        readiness = evaluate_publication_readiness(playback_video_url, job_extra_data)
        preview_export = _can_export_preview_package(readiness, job_extra_data, metadata)
        if not readiness["is_publishable"] and not preview_export:
            _raise_publication_not_ready(readiness)
    else:
        readiness = evaluate_publication_readiness(playback_video_url, metadata)
        if not readiness["is_publishable"]:
            _raise_publication_not_ready(readiness)
    visibility = str(metadata.get("visibility") or "private")
    if visibility not in {"private", "project", "public"}:
        visibility = "private"
    source_manifest_url = render_artifacts.get("source_manifest_url") or job_extra_data.get("manifest_url")
    artifact_payload = {
        "id": export_id,
        "title": title,
        "provider": "local",
        "project_id": project_id,
        "synthesis_job_id": synthesis_job.id if synthesis_job else None,
        "source_output_url": playback_video_url,
        "video_url": render_artifacts.get("preview_url") if preview_export else playback_video_url,
        "cover_url": synthesis_job.cover_url if synthesis_job else metadata.get("cover_url"),
        "duration_seconds": synthesis_job.duration_seconds if synthesis_job else metadata.get("duration_seconds"),
        "metadata": metadata,
        "created_at": utc_now().isoformat(),
    }
    if synthesis_job:
        artifact_payload.update(
            {
                "render_artifacts": render_artifacts,
                "preview_url": render_artifacts.get("preview_url"),
                "srt_url": render_artifacts.get("srt_url"),
                "timeline_url": render_artifacts.get("timeline_url"),
                "render_manifest_url": render_artifacts.get("render_manifest_url"),
                "source_manifest_url": source_manifest_url,
                "render_status": job_extra_data.get("render_status"),
                "render_backend": job_extra_data.get("render_backend"),
                "render_source": job_extra_data.get("render_source"),
                "timeline_id": job_extra_data.get("render_timeline_id") or job_extra_data.get("timeline_id"),
                "is_publishable": False if preview_export else True,
                "output_kind": "preview_package" if preview_export else "final_video",
                "preview_export": preview_export,
            }
        )
    publication_provider = await _apply_publication_storage_delivery(db, user_id, artifact_payload)
    publication_video_url = artifact_payload.get("video_url")
    artifact_path, local_export_url = write_local_export_artifact(export_id, artifact_payload)
    publication_provider, export_url = await _apply_export_artifact_storage_delivery(
        db,
        user_id,
        artifact_payload,
        local_export_url=local_export_url,
        current_provider=publication_provider,
    )
    artifact_payload["provider"] = publication_provider
    artifact_payload["export_url"] = export_url
    artifact_path.write_text(json.dumps(artifact_payload, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")

    publication = Publication(
        id=export_id,
        user_id=user_id,
        project_id=project_id,
        synthesis_job_id=synthesis_job.id if synthesis_job else None,
        title=title,
        status="succeeded",
        visibility=visibility,
        video_url=publication_video_url,
        cover_url=synthesis_job.cover_url if synthesis_job else metadata.get("cover_url"),
        duration_seconds=synthesis_job.duration_seconds if synthesis_job else metadata.get("duration_seconds"),
        format=metadata.get("format") or ("html" if preview_export else "mp4"),
        resolution=metadata.get("resolution") or "1080p",
        export_url=export_url,
        artifact_path=str(artifact_path),
        provider=publication_provider,
        publication_metadata=artifact_payload,
    )
    db.add(publication)
    await db.commit()
    await db.refresh(publication)
    return build_publication_response(publication)


@router.get("/publications", response_model=List[PublicationResponse])
async def list_publications(
    project_id: Optional[str] = None,
    synthesis_job_id: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    include_archived: bool = False,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取发布/导出记录列表。"""
    query = select(Publication).where(Publication.user_id == user_id)
    if project_id:
        await require_project_role(db, project_id, user_id, "viewer")
        query = query.where(Publication.project_id == project_id)
    if synthesis_job_id:
        query = query.where(Publication.synthesis_job_id == synthesis_job_id)
    if status_filter:
        query = query.where(Publication.status == status_filter)
    elif not include_archived:
        query = query.where(Publication.status != "archived")
    result = await db.execute(query.order_by(desc(Publication.created_at)).limit(limit))
    return [build_publication_response(item) for item in result.scalars().all()]


@router.get("/publications/{publication_id}", response_model=PublicationResponse)
async def get_publication(
    publication_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    publication = await get_publication_or_404(db, publication_id, user_id)
    if publication.project_id:
        await require_project_role(db, publication.project_id, user_id, "viewer")
    return build_publication_response(publication)


@router.put("/publications/{publication_id}", response_model=PublicationResponse)
async def update_publication(
    publication_id: str,
    request: PublicationUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    publication = await get_publication_or_404(db, publication_id, user_id)
    if publication.project_id:
        await require_project_role(db, publication.project_id, user_id, "editor")

    if request.title is not None:
        publication.title = request.title
    if request.status is not None:
        if request.status not in {"succeeded", "draft", "published", "revoked", "archived"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="不支持的发布状态")
        publication.status = request.status
    if request.metadata is not None:
        publication.publication_metadata = {
            **(publication.publication_metadata or {}),
            "metadata": request.metadata,
        }

    await db.commit()
    await db.refresh(publication)
    return build_publication_response(publication)


@router.post("/publications/{publication_id}/revoke", response_model=PublicationResponse)
async def revoke_publication(
    publication_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    publication = await get_publication_or_404(db, publication_id, user_id)
    if publication.project_id:
        await require_project_role(db, publication.project_id, user_id, "editor")
    publication.status = "revoked"
    await db.commit()
    await db.refresh(publication)
    return build_publication_response(publication)


@router.delete("/publications/{publication_id}")
async def delete_publication(
    publication_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    publication = await get_publication_or_404(db, publication_id, user_id)
    if publication.project_id:
        await require_project_role(db, publication.project_id, user_id, "editor")
    publication.status = "archived"
    await db.commit()
    return {"message": "发布记录已归档", "publication_id": publication_id}


@router.post("/execute", response_model=SynthesisExecuteResponse)
async def execute_synthesis(
    request: SynthesisExecuteRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """执行真实FFmpeg合成：拼接视频+音频混合+字幕烧录+封面生成"""
    if not request.video_urls:
        raise HTTPException(status_code=422, detail="video_urls不能为空")

    # 权限检查
    if request.project_id:
        await require_project_role(db, request.project_id, user_id, "editor")

    # 转换字幕格式
    subtitles = None
    if request.subtitles:
        from app.services.synthesis_executor import SubtitleSegment
        subtitles = [
            SubtitleSegment(
                text=seg.text,
                start_time=seg.start_time,
                end_time=seg.end_time,
                style=seg.style
            )
            for seg in request.subtitles
        ]

    # 执行合成
    from app.services.synthesis_executor import SynthesisExecutor
    executor = SynthesisExecutor()

    result = await executor.synthesize(
        video_urls=request.video_urls,
        audio_urls=request.audio_urls,
        subtitles=subtitles,
        output_format=request.output_format,
        quality=request.quality
    )

    # 创建合成任务记录
    job_id = result["job_id"]
    synthesis_job = SynthesisJob(
        id=job_id,
        user_id=user_id,
        project_id=request.project_id,
        workflow_id=request.workflow_id,
        title=request.title or "FFmpeg合成",
        model_id="ffmpeg-synthesis",
        model_name="FFmpeg本地合成",
        video_url=request.video_urls[0],
        audio_url=request.audio_urls[0] if request.audio_urls else None,
        status=result["status"],
        progress=100 if result["status"] == "succeeded" else 0,
        output_url=result.get("video_url"),
        cover_url=result.get("cover_url"),
        duration_seconds=result.get("duration_seconds"),
        extra_data={
            "output_format": request.output_format,
            "quality": request.quality,
            "source_video_urls": request.video_urls,
            "source_audio_urls": request.audio_urls or [],
        }
    )
    db.add(synthesis_job)
    await db.commit()

    return SynthesisExecuteResponse(
        job_id=job_id,
        status=result["status"],
        video_url=result.get("video_url"),
        cover_url=result.get("cover_url"),
        duration_seconds=result.get("duration_seconds"),
        error=result.get("error")
    )


@router.post("/synthesize", response_model=SynthesisJobResponse)
async def synthesize_video(
    request: SynthesisExecuteRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """完整合成流程：创建合成任务并执行真实FFmpeg合成"""
    if not request.video_urls:
        raise HTTPException(status_code=422, detail="video_urls不能为空")

    # 权限检查
    if request.project_id:
        await require_project_role(db, request.project_id, user_id, "editor")

    # 转换字幕格式
    subtitles = None
    if request.subtitles:
        from app.services.synthesis_executor import SubtitleSegment
        subtitles = [
            SubtitleSegment(
                text=seg.text,
                start_time=seg.start_time,
                end_time=seg.end_time,
                style=seg.style
            )
            for seg in request.subtitles
        ]

    # 执行合成
    from app.services.synthesis_executor import SynthesisExecutor
    executor = SynthesisExecutor()

    result = await executor.synthesize(
        video_urls=request.video_urls,
        audio_urls=request.audio_urls,
        subtitles=subtitles,
        output_format=request.output_format,
        quality=request.quality
    )

    # 创建合成任务记录
    job_id = result["job_id"]
    synthesis_job = SynthesisJob(
        id=job_id,
        user_id=user_id,
        project_id=request.project_id,
        workflow_id=request.workflow_id,
        title=request.title or "完整合成",
        model_id="ffmpeg-synthesis",
        model_name="FFmpeg本地合成",
        video_url=request.video_urls[0] if request.video_urls else None,
        audio_url=request.audio_urls[0] if request.audio_urls else None,
        status=result["status"],
        progress=100 if result["status"] == "succeeded" else 0,
        output_url=result.get("video_url"),
        cover_url=result.get("cover_url"),
        duration_seconds=result.get("duration_seconds"),
        extra_data={
            "output_format": request.output_format,
            "quality": request.quality,
            "video_urls": request.video_urls,
            "audio_urls": request.audio_urls,
        }
    )
    db.add(synthesis_job)
    await db.commit()
    await db.refresh(synthesis_job)

    return build_synthesis_response(synthesis_job)


@router.post("/publications/{publication_id}/publish", response_model=PublicationResponse)
async def publish_video(
    publication_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """发布作品"""
    publication = await get_publication_or_404(db, publication_id, user_id)
    if publication.project_id:
        await require_project_role(db, publication.project_id, user_id, "editor")
    publication.status = "published"
    await db.commit()
    await db.refresh(publication)
    return build_publication_response(publication)


@router.get("/publications/{publication_id}/download")
async def download_publication(
    publication_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取发布作品下载信息"""
    publication = await get_publication_or_404(db, publication_id, user_id)
    if publication.project_id:
        await require_project_role(db, publication.project_id, user_id, "viewer")

    # 增加下载计数
    publication.view_count = (publication.view_count or 0) + 1
    await db.commit()

    return {
        "id": publication.id,
        "title": publication.title,
        "video_url": publication.video_url,
        "cover_url": publication.cover_url,
        "format": publication.format,
        "resolution": publication.resolution,
        "duration_seconds": publication.duration_seconds,
    }


@router.get("/jobs", response_model=List[SynthesisJobResponse])
async def list_synthesis_jobs(
    limit: int = Query(50, ge=1, le=200),
    project_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    render_status: Optional[str] = None,
    novel_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    script_id: Optional[str] = None,
    storyboard_id: Optional[str] = None,
    shot_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取用户的合成任务列表"""
    query = select(SynthesisJob).where(SynthesisJob.user_id == user_id)
    if project_id:
        query = query.where(SynthesisJob.project_id == project_id)
    if workflow_id:
        query = query.where(SynthesisJob.workflow_id == workflow_id)
    if status_filter:
        query = query.where(SynthesisJob.status == status_filter)
    query = query.order_by(desc(SynthesisJob.created_at))
    has_extra_filters = any([render_status, novel_id, chapter_id, script_id, storyboard_id, shot_id])
    if not has_extra_filters:
        query = query.limit(limit)
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    if has_extra_filters:
        lineage_filters = {
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": script_id,
            "storyboard_id": storyboard_id,
            "shot_id": shot_id,
        }
        jobs = [
            job
            for job in jobs
            if _synthesis_job_matches_filters(
                job,
                status_filter=None,
                render_status=render_status,
                lineage_filters=lineage_filters,
            )
        ][:limit]

    return [build_synthesis_response(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=SynthesisJobResponse)
async def get_synthesis_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取合成任务详情"""
    query = select(SynthesisJob).where(
        SynthesisJob.id == job_id,
        SynthesisJob.user_id == user_id
    )
    
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return build_synthesis_response(job)


@router.put("/jobs/{job_id}", response_model=SynthesisJobResponse)
async def update_synthesis_job(
    job_id: str,
    update: SynthesisStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新合成任务状态"""
    query = select(SynthesisJob).where(
        SynthesisJob.id == job_id,
        SynthesisJob.user_id == user_id
    )
    
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 更新字段
    if update.status:
        job.status = update.status
    if update.progress is not None:
        job.progress = update.progress
    if update.output_url:
        job.output_url = update.output_url
    if update.error_message:
        job.error_message = update.error_message
    
    await db.commit()
    await db.refresh(job)
    
    return build_synthesis_response(job)


@router.delete("/jobs/{job_id}")
async def delete_synthesis_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除合成任务"""
    query = select(SynthesisJob).where(
        SynthesisJob.id == job_id,
        SynthesisJob.user_id == user_id
    )
    
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    await db.delete(job)
    await db.commit()
    
    return {"message": "删除成功"}
