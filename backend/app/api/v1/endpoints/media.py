"""
Unified media generation API.

P0 focuses on direct shot audio-video generation and the compatibility layer
that lets existing video/TTS/synthesis workflows continue to work.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints import subtitles as subtitle_api
from app.api.v1.endpoints.video import VideoGenerateRequest, _resolve_video_lineage
from app.core.database import get_db
from app.core.dev_generation import dev_audio_url, dev_video_url, is_dev_mode
from app.core.model_registry import get_model, get_task_default
from app.core.security import get_current_user_id
from app.core.time_utils import utc_now
from app.models.external_api import ExternalAPIConfig, ExternalAPIProvider
from app.models.media_generation_job import MediaGenerationJob
from app.models.subtitle import SubtitleSegment, SubtitleTrack
from app.services.consistency_preflight import build_generation_context_package, preflight_failure_detail
from app.services.story_prompt_context import build_video_continuity_constraints, load_story_prompt_context

router = APIRouter(tags=["统一媒体生成"])


class MediaGenerateRequest(BaseModel):
    task_type: str = Field("shot_audio_video", description="shot_audio_video/shot_video/tts_dialogue/final_render")
    media_type: str = Field("audio_video", description="video/audio/audio_video/subtitle/timeline/render_package")
    prompt: str = Field(..., min_length=1)
    title: Optional[str] = None
    provider_id: Optional[str] = None
    model_id: Optional[str] = None
    duration: int = Field(5, ge=1, le=60)
    resolution: str = "720p"
    seed: Optional[int] = None
    project_id: Optional[str] = None
    workflow_id: Optional[str] = None
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    storyboard_id: Optional[str] = None
    shot_id: Optional[str] = None
    story_bible_id: Optional[str] = None
    reference_asset_ids: List[str] = Field(default_factory=list)
    input_assets: List[Dict[str, Any]] = Field(default_factory=list)
    subtitle_mode: str = Field("shot_dialogue", description="shot_dialogue/direct_model/off")
    audio_mode: str = Field("model_audio", description="model_audio/tts/none")
    use_consistency_context: bool = True
    unsafe_skip_consistency_preflight: bool = Field(False, description="仅用于明确的生产降级调试：跳过一致性预检")
    external_config_id: Optional[str] = Field(None, description="外部生产适配配置ID")
    adapter_options: Dict[str, Any] = Field(default_factory=dict, description="供应商/插件适配参数")
    asset_version_locks: List[Dict[str, Any]] = Field(default_factory=list, description="资产版本锁")
    keyframes: List[Dict[str, Any]] = Field(default_factory=list, description="关键帧控制")
    character_multiview_refs: List[Dict[str, Any]] = Field(default_factory=list, description="角色多视图参考")
    lip_sync_mode: str = Field("off", description="off/provider/model_audio")
    review_required: bool = Field(False, description="生成后是否进入多人审核")


class MediaJobResponse(BaseModel):
    id: str
    task_id: Optional[str] = None
    task_type: str
    media_type: str
    title: Optional[str] = None
    prompt: Optional[str] = None
    provider_id: Optional[str] = None
    model_id: Optional[str] = None
    model_name: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    project_id: Optional[str] = None
    workflow_id: Optional[str] = None
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    storyboard_id: Optional[str] = None
    shot_id: Optional[str] = None
    duration_seconds: Optional[float] = None
    resolution: Optional[str] = None
    seed: Optional[int] = None
    output_video_url: Optional[str] = None
    output_audio_url: Optional[str] = None
    output_manifest_url: Optional[str] = None
    subtitle_track_id: Optional[str] = None
    timeline_id: Optional[str] = None
    cover_url: Optional[str] = None
    status: str
    progress: int
    error_message: Optional[str] = None
    quality_report: Dict[str, Any] = Field(default_factory=dict)
    extra_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


def _json_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _job_response(job: MediaGenerationJob) -> MediaJobResponse:
    return MediaJobResponse(
        id=job.id,
        task_id=job.task_id,
        task_type=job.task_type,
        media_type=job.media_type,
        title=job.title,
        prompt=job.prompt,
        provider_id=job.provider_id,
        model_id=job.model_id,
        model_name=job.model_name,
        capabilities=job.capabilities or [],
        project_id=job.project_id,
        workflow_id=job.workflow_id,
        novel_id=job.novel_id,
        chapter_id=job.chapter_id,
        script_id=job.script_id,
        storyboard_id=job.storyboard_id,
        shot_id=job.shot_id,
        duration_seconds=job.duration_seconds,
        resolution=job.resolution,
        seed=job.seed,
        output_video_url=job.output_video_url,
        output_audio_url=job.output_audio_url,
        output_manifest_url=job.output_manifest_url,
        subtitle_track_id=job.subtitle_track_id,
        timeline_id=job.timeline_id,
        cover_url=job.cover_url,
        status=job.status,
        progress=job.progress or 0,
        error_message=job.error_message,
        quality_report=_json_dict(job.quality_report),
        extra_data=_json_dict(job.extra_data),
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _resolve_model_for_task(task_type: str, requested_model_id: Optional[str]) -> Dict[str, Any]:
    model = get_model(requested_model_id) if requested_model_id else None
    if model:
        return model
    task_default = get_task_default({"final_render": "cloud_render"}.get(task_type, task_type))
    if task_default and task_default.get("default_model"):
        return task_default["default_model"]
    fallback = get_task_default("shot_audio_video")
    if fallback and fallback.get("default_model"):
        return fallback["default_model"]
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="未找到可用的媒体生成模型")


def _allowed_task_types() -> set[str]:
    return {"shot_audio_video", "comfyui_workflow", "lip_sync_video", "final_render", "cloud_render"}


async def _get_external_config(
    db: AsyncSession,
    user_id: str,
    config_id: Optional[str],
    provider_id: Optional[str],
) -> tuple[Optional[ExternalAPIConfig], Optional[ExternalAPIProvider]]:
    if config_id:
        result = await db.execute(
            select(ExternalAPIConfig, ExternalAPIProvider)
            .join(ExternalAPIProvider, ExternalAPIConfig.provider_id == ExternalAPIProvider.id)
            .where(
                ExternalAPIConfig.id == config_id,
                ExternalAPIConfig.user_id == user_id,
                ExternalAPIConfig.is_active == True,
            )
        )
        row = result.first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="外部生产适配配置不存在")
        return row[0], row[1]

    if not provider_id:
        return None, None
    result = await db.execute(
        select(ExternalAPIConfig, ExternalAPIProvider)
        .join(ExternalAPIProvider, ExternalAPIConfig.provider_id == ExternalAPIProvider.id)
        .where(
            ExternalAPIConfig.user_id == user_id,
            ExternalAPIConfig.is_active == True,
            ExternalAPIProvider.name == provider_id,
        )
        .order_by(ExternalAPIConfig.is_default.desc(), ExternalAPIConfig.created_at.desc())
        .limit(1)
    )
    row = result.first()
    return (row[0], row[1]) if row else (None, None)


async def _submit_external_adapter_job(
    *,
    config: ExternalAPIConfig,
    provider: ExternalAPIProvider,
    job_id: str,
    payload: Dict[str, Any],
) -> tuple[Optional[str], str, Dict[str, Any]]:
    extra = config.extra_config or {}
    base_url = (config.custom_base_url or provider.base_url or "").rstrip("/")
    submit_path = extra.get("submit_path")
    if provider.name == "comfyui":
        submit_path = submit_path or "/prompt"
    if not base_url or not submit_path:
        return None, "adapter_ready", {"message": "缺少 base_url 或 submit_path，任务已保存为待外部适配提交"}

    headers: Dict[str, str] = {"Content-Type": "application/json"}
    api_key = config.get_api_key_decrypted()
    if api_key and provider.auth_type != "none":
        header_name = provider.auth_header or "Authorization"
        headers[header_name] = f"Bearer {api_key}" if provider.auth_type == "bearer" else api_key

    request_body = payload
    if provider.name == "comfyui":
        request_body = {
            "client_id": job_id,
            "prompt": payload.get("workflow_json") or extra.get("workflow_template") or {},
            "extra_data": payload,
        }

    async with httpx.AsyncClient(timeout=config.timeout or 60) as client:
        response = await client.post(f"{base_url}{submit_path}", headers=headers, json=request_body)
    if response.status_code >= 400:
        return None, "failed", {"status_code": response.status_code, "body": response.text[:1000]}
    data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    task_id = str(data.get("prompt_id") or data.get("task_id") or data.get("id") or "")
    return task_id or None, "pending", {"response": data}


async def _create_subtitle_for_media_job(
    db: AsyncSession,
    user_id: str,
    job: MediaGenerationJob,
    subtitle_text: str,
    source: str,
) -> Optional[str]:
    text = subtitle_text.strip()
    if not text:
        return None
    track = SubtitleTrack(
        id=str(uuid4()),
        user_id=user_id,
        project_id=job.project_id,
        workflow_id=job.workflow_id,
        novel_id=job.novel_id,
        chapter_id=job.chapter_id,
        script_id=job.script_id,
        storyboard_id=job.storyboard_id,
        shot_id=job.shot_id,
        media_job_id=job.id,
        title=f"{job.title or '音视频任务'} 字幕",
        language="zh-CN",
        kind="dialogue",
        source=source,
        status="draft",
        metadata_={"media_job_id": job.id, "task_type": job.task_type},
    )
    segment = SubtitleSegment(
        id=str(uuid4()),
        track_id=track.id,
        user_id=user_id,
        shot_id=job.shot_id,
        start_seconds=0.0,
        end_seconds=float(job.duration_seconds or 4),
        text=text,
        original_text=text,
        source=source,
        confidence=1.0,
        review_status="pending_review",
        sort_order=1,
    )
    db.add(track)
    db.add(segment)
    job.subtitle_track_id = track.id
    return track.id


async def _sync_media_job_to_workflow(db: AsyncSession, job: MediaGenerationJob, user_id: str) -> None:
    if not job.workflow_id:
        return
    from app.models.workflow import Workflow

    result = await db.execute(select(Workflow).where(Workflow.id == job.workflow_id, Workflow.user_id == user_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        return
    media_jobs = list((_json_dict(workflow.metadata_).get("media_job_ids") or []))
    media_jobs.append(job.id)
    workflow.metadata_ = {
        **_json_dict(workflow.metadata_),
        "media_job_ids": list(dict.fromkeys(media_jobs)),
        "latest_media_job_id": job.id,
        "latest_media_task_type": job.task_type,
        "latest_subtitle_track_id": job.subtitle_track_id,
    }


@router.post("/generate", response_model=MediaJobResponse)
async def generate_media(
    request: MediaGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    if request.task_type not in _allowed_task_types():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"当前支持的生产媒体任务: {', '.join(sorted(_allowed_task_types()))}",
        )

    lineage_request = VideoGenerateRequest(
        prompt=request.prompt,
        model="Doubao-Seedance-1.0-pro-fast",
        duration=max(4, min(request.duration, 10)),
        resolution=request.resolution,
        project_id=request.project_id,
        workflow_id=request.workflow_id,
        novel_id=request.novel_id,
        chapter_id=request.chapter_id,
        script_id=request.script_id,
        storyboard_id=request.storyboard_id,
        shot_id=request.shot_id,
        story_bible_id=request.story_bible_id,
        use_consistency_context=request.use_consistency_context,
    )
    lineage = await _resolve_video_lineage(db, user_id, lineage_request)
    shot = lineage.get("shot")
    shot_extra = _json_dict(getattr(shot, "extra_data", None))
    model = _resolve_model_for_task(request.task_type, request.model_id)

    if not is_dev_mode() and not request.use_consistency_context and not request.unsafe_skip_consistency_preflight:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="生产模式不能跳过一致性预检；如需降级调试，请显式开启 unsafe_skip_consistency_preflight 并记录原因。",
        )
    preflight_package = None
    if not is_dev_mode() and not request.unsafe_skip_consistency_preflight:
        preflight_package = await build_generation_context_package(
            db,
            user_id,
            task_type="direct_audio_video" if request.task_type == "shot_audio_video" else request.task_type,
            external_config_id=request.external_config_id,
            production_mode=True,
            novel_id=request.novel_id,
            chapter_id=request.chapter_id,
            script_id=request.script_id,
            storyboard_id=request.storyboard_id,
            shot_id=request.shot_id,
        )
        if not preflight_package.get("ready"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=preflight_failure_detail(preflight_package),
            )

    external_config, external_provider = await _get_external_config(
        db,
        user_id,
        request.external_config_id,
        request.provider_id or model.get("provider_id"),
    )
    final_prompt = request.prompt
    story_constraints = ""
    if request.use_consistency_context:
        story_prompt_context = await load_story_prompt_context(
            db,
            user_id,
            novel_id=lineage.get("novel_id"),
            chapter_id=lineage.get("chapter_id"),
        )
        story_constraints = build_video_continuity_constraints(story_prompt_context)
        final_prompt = f"{request.prompt}\n\n{story_constraints}"

    subtitle_text = ""
    if request.subtitle_mode != "off":
        subtitle_text = (shot_extra.get("subtitle_text") if shot else None) or (getattr(shot, "dialogue", None) if shot else None) or ""

    job_id = str(uuid4())
    video_url = dev_video_url(job_id, duration_seconds=request.duration) if is_dev_mode() else None
    audio_url = dev_audio_url(job_id) if is_dev_mode() and request.audio_mode != "none" else None
    capabilities = list(model.get("capabilities") or [])
    lineage_payload = {
        key: lineage.get(key)
        for key in (
            "project_id",
            "workflow_id",
            "novel_id",
            "chapter_id",
            "script_id",
            "storyboard_id",
            "shot_id",
            "novel_title",
            "chapter_title",
            "script_title",
            "storyboard_title",
            "shot_number",
        )
    }
    adapter_payload = {
        "job_id": job_id,
        "task_type": request.task_type,
        "media_type": request.media_type,
        "prompt": final_prompt,
        "duration": request.duration,
        "resolution": request.resolution,
        "lineage": lineage_payload,
        "asset_version_locks": request.asset_version_locks,
        "keyframes": request.keyframes or getattr(shot, "keyframes", None) or [],
        "character_multiview_refs": request.character_multiview_refs,
        "lip_sync_mode": request.lip_sync_mode,
        "adapter_options": request.adapter_options,
        "workflow_json": request.adapter_options.get("workflow_json") if isinstance(request.adapter_options, dict) else None,
    }
    provider_task_id = f"dev-media-{job_id}"
    status_value = "succeeded" if is_dev_mode() else "adapter_ready"
    progress_value = 100 if is_dev_mode() else 10
    adapter_result: Dict[str, Any] = {}
    if not is_dev_mode():
        if not external_config or not external_provider:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="真实生产适配需要先在外部能力管理中配置对应供应商",
            )
        provider_task_id, status_value, adapter_result = await _submit_external_adapter_job(
            config=external_config,
            provider=external_provider,
            job_id=job_id,
            payload=adapter_payload,
        )
        progress_value = 10 if status_value in {"pending", "adapter_ready"} else 0
    job = MediaGenerationJob(
        id=job_id,
        user_id=user_id,
        project_id=lineage.get("project_id"),
        workflow_id=lineage.get("workflow_id"),
        task_id=provider_task_id,
        task_type=request.task_type,
        media_type=request.media_type,
        title=request.title or (f"镜头 {lineage.get('shot_number')} 音视频直生" if lineage.get("shot_number") else "音视频直生"),
        prompt=final_prompt,
        provider_id=(external_provider.name if external_provider else None) or request.provider_id or model.get("provider_id"),
        model_id=model.get("id"),
        model_name=f"{model.get('display_name', model.get('id'))} {'(DEV_MODE)' if is_dev_mode() else '(外部适配)'}",
        capabilities=capabilities,
        novel_id=lineage.get("novel_id"),
        chapter_id=lineage.get("chapter_id"),
        script_id=lineage.get("script_id"),
        storyboard_id=lineage.get("storyboard_id"),
        shot_id=lineage.get("shot_id"),
        duration_seconds=float(request.duration),
        resolution=request.resolution,
        seed=request.seed,
        input_assets=request.input_assets or [{"asset_id": asset_id} for asset_id in request.reference_asset_ids],
        source_job_ids={},
        output_video_url=video_url,
        output_audio_url=audio_url,
        cover_url=getattr(shot, "image_url", None) if shot else None,
        status=status_value,
        progress=progress_value,
        quality_report={
            "mode": "dev_placeholder" if is_dev_mode() else "external_adapter",
            "warnings": (
                ["DEV_MODE 使用本地占位音视频文件，不代表真实供应商生成质量"]
                if is_dev_mode()
                else ["外部适配任务已保存/提交，最终产物需等待供应商回调或轮询"]
            ),
            "subtitle_required": request.subtitle_mode != "off",
            "review_required": request.review_required,
        },
        extra_data={
            "lineage": lineage_payload,
            "subtitle_text": subtitle_text,
            "source_prompt": request.prompt,
            "story_continuity_constraints": story_constraints,
            "subtitle_mode": request.subtitle_mode,
            "audio_mode": request.audio_mode,
            "external_config_id": external_config.id if external_config else request.external_config_id,
            "external_provider_id": external_provider.id if external_provider else None,
            "adapter_payload": adapter_payload,
            "adapter_result": adapter_result,
            "asset_version_locks": request.asset_version_locks,
            "keyframes": adapter_payload["keyframes"],
            "character_multiview_refs": request.character_multiview_refs,
            "lip_sync_mode": request.lip_sync_mode,
            "review": {
                "required": request.review_required,
                "state": "pending_review" if request.review_required else "auto_accepted",
            },
            "reference_asset_ids": request.reference_asset_ids,
            "provider_audio_metadata": {
                "has_audio": bool(audio_url),
                "source": "direct_av_model" if audio_url else ("external_adapter" if not is_dev_mode() else "none"),
            },
            **(
                {
                    "generation_preflight": {
                        "ready": preflight_package.get("ready"),
                        "issues": preflight_package.get("issues") or [],
                        "blocking_issue_count": preflight_package.get("blocking_issue_count") or 0,
                    }
                }
                if preflight_package is not None
                else {}
            ),
        },
    )
    db.add(job)
    if subtitle_text and request.subtitle_mode != "off":
        await _create_subtitle_for_media_job(db, user_id, job, subtitle_text, "direct_av_model")

    if shot and is_dev_mode():
        shot.video_url = video_url
        shot.video_status = "succeeded"
        if audio_url:
            shot.audio_url = audio_url
            shot.audio_status = "succeeded"
        shot.extra_data = {
            **shot_extra,
            "latest_media_job_id": job.id,
            "latest_subtitle_track_id": job.subtitle_track_id,
        }
    elif shot:
        shot.extra_data = {
            **shot_extra,
            "latest_media_job_id": job.id,
            "latest_external_media_status": status_value,
        }

    await _sync_media_job_to_workflow(db, job, user_id)
    await db.commit()
    await db.refresh(job)
    return _job_response(job)


@router.get("/jobs", response_model=List[MediaJobResponse])
async def list_media_jobs(
    task_type: Optional[str] = None,
    media_type: Optional[str] = None,
    workflow_id: Optional[str] = None,
    novel_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    script_id: Optional[str] = None,
    storyboard_id: Optional[str] = None,
    shot_id: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    query = select(MediaGenerationJob).where(MediaGenerationJob.user_id == user_id, MediaGenerationJob.is_active == True)
    if task_type:
        query = query.where(MediaGenerationJob.task_type == task_type)
    if media_type:
        query = query.where(MediaGenerationJob.media_type == media_type)
    if workflow_id:
        query = query.where(MediaGenerationJob.workflow_id == workflow_id)
    if novel_id:
        query = query.where(MediaGenerationJob.novel_id == novel_id)
    if chapter_id:
        query = query.where(MediaGenerationJob.chapter_id == chapter_id)
    if script_id:
        query = query.where(MediaGenerationJob.script_id == script_id)
    if storyboard_id:
        query = query.where(MediaGenerationJob.storyboard_id == storyboard_id)
    if shot_id:
        query = query.where(MediaGenerationJob.shot_id == shot_id)
    if status_filter:
        query = query.where(MediaGenerationJob.status == status_filter)
    result = await db.execute(query.order_by(desc(MediaGenerationJob.created_at)).limit(100))
    return [_job_response(job) for job in result.scalars().all()]


@router.get("/jobs/{job_id}", response_model=MediaJobResponse)
async def get_media_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(
        select(MediaGenerationJob).where(MediaGenerationJob.id == job_id, MediaGenerationJob.user_id == user_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="媒体任务不存在")
    return _job_response(job)


@router.post("/jobs/{job_id}/cancel", response_model=MediaJobResponse)
async def cancel_media_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """取消本地跟踪的统一媒体任务。外部供应商取消能力由适配器单独实现。"""
    result = await db.execute(
        select(MediaGenerationJob).where(
            MediaGenerationJob.id == job_id,
            MediaGenerationJob.user_id == user_id,
            MediaGenerationJob.is_active == True,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="媒体任务不存在")
    if job.status in {"succeeded", "completed"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已完成任务不能取消")

    job.status = "cancelled"
    job.progress = job.progress or 0
    job.error_message = job.error_message or "任务已由用户取消"
    job.updated_at = utc_now()
    await db.commit()
    await db.refresh(job)
    return _job_response(job)


@router.delete("/jobs/{job_id}")
async def delete_media_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """软删除统一媒体任务，保留记录用于审计和后续恢复。"""
    result = await db.execute(
        select(MediaGenerationJob).where(
            MediaGenerationJob.id == job_id,
            MediaGenerationJob.user_id == user_id,
            MediaGenerationJob.is_active == True,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="媒体任务不存在")

    job.is_active = False
    job.status = "archived"
    job.updated_at = utc_now()
    await db.commit()
    return {"message": "媒体任务已归档", "job_id": job_id}


@router.post("/jobs/{job_id}/export-subtitles")
async def export_media_job_subtitles(
    job_id: str,
    format: str = Query("srt", pattern="^(srt|vtt|ass)$"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(
        select(MediaGenerationJob).where(MediaGenerationJob.id == job_id, MediaGenerationJob.user_id == user_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="媒体任务不存在")
    if not job.subtitle_track_id:
        extra = _json_dict(job.extra_data)
        subtitle_text = extra.get("subtitle_text") or ""
        if not subtitle_text:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="媒体任务没有字幕轨")
        await _create_subtitle_for_media_job(db, user_id, job, subtitle_text, "direct_av_model")
        await db.commit()
        await db.refresh(job)

    export_request = subtitle_api.ExportSubtitleRequest(format=format)
    return await subtitle_api.export_subtitle_track(job.subtitle_track_id, export_request, db, user_id)
