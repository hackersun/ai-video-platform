"""Direct audio-video workflow-media application use case."""

from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import uuid4

from app.core.dev_generation import dev_audio_url, dev_video_url, is_dev_mode
from app.core.model_registry import get_task_default
from app.core.time_utils import utc_now
from app.features.workflow_media.application.load_context import WorkflowMediaContext
from app.features.workflow_media.application.voice_locks import (
    FinalQualityLockCommand,
    build_final_quality_lock_snapshots,
)
from app.features.workflow_media.domain.production_strategy import (
    merge_latest_production_strategy,
    production_strategy_job_extra,
)
from app.features.workflow_media.domain.workflow_state import complete_steps
from app.features.workflow_media.errors import WorkflowMediaError
from app.features.workflow_media.repositories import workflow_media_repository as repository
from app.features.workflow_media.schemas import WorkflowMediaBatchRequest, WorkflowMediaBatchResponse
from app.models import Shot
from app.models.media_generation_job import MediaGenerationJob
from app.models.subtitle import SubtitleSegment, SubtitleTrack
from app.services.deterministic_provider_fake import (
    deterministic_media_provider_artifacts,
    deterministic_provider_fake_enabled,
)


@dataclass(frozen=True)
class DirectAvCommand:
    context: WorkflowMediaContext
    request: WorkflowMediaBatchRequest


@dataclass
class _BatchState:
    media_job_ids: list[str]
    subtitle_track_ids: list[str]
    lock_snapshots: Dict[str, Dict[str, Any]]
    runtime_model: Dict[str, Any]


def _extra(shot: Shot) -> dict:
    return shot.extra_data if isinstance(shot.extra_data, dict) else {}


async def _resolve_runtime_model(context: WorkflowMediaContext) -> Dict[str, Any]:
    config_id = context.effective_video_config_id
    selected = None
    if config_id:
        row = await repository.get_video_model_config(context.db, context.user_id, config_id)
        if row is None:
            raise WorkflowMediaError(404, "所选视频模型配置不存在或已停用")
        config, model, provider = row
        capabilities = [str(item).lower() for item in (model.capabilities or [])]
        model_type = (model.model_type or "").lower()
        if model_type not in {"video", "video-generation", "video_generation"} and not any(
            "video" in item for item in capabilities
        ):
            raise WorkflowMediaError(422, "所选模型配置不支持视频生成能力")
        selected = {
            "provider_id": provider.name or provider.id,
            "model_id": model.model_id,
            "model_name": model.model_name_cn or model.model_name,
            "capabilities": model.capabilities or [],
            "test_status": config.test_status,
        }
    default = (get_task_default("shot_audio_video") or {}).get("default_model") or {}
    return selected or {
        "provider_id": default.get("provider_id", "local"),
        "model_id": default.get("id", "local.dev_audio_video"),
        "model_name": f"{default.get('display_name', 'DEV_MODE 音视频直生')} (DEV_MODE)",
        "capabilities": default.get("capabilities") or ["text_to_audio_video", "shot_audio_video"],
    }


async def _load_lock_snapshots(
    context: WorkflowMediaContext, request: WorkflowMediaBatchRequest,
) -> Dict[str, Dict[str, Any]]:
    if request.production_strategy != "final_quality":
        return {}
    return await build_final_quality_lock_snapshots(FinalQualityLockCommand(
        context.db,
        context.user_id,
        context.workflow,
        context.shots,
        requested_story_bible_id=request.story_bible_id,
        default_voice=request.voice_model,
        default_speed=request.speed,
        default_voice_source="provider_default_tts",
    ))


def _shot_inputs(shot: Shot, request: WorkflowMediaBatchRequest, locks: dict) -> dict:
    shot_extra = _extra(shot)
    production = shot_extra.get("production_context")
    production = production if isinstance(production, dict) else {}
    asset_locks = production.get("asset_version_locks")
    asset_locks = asset_locks if isinstance(asset_locks, list) else []
    snapshot = locks.get(shot.id) or {}
    return {
        "extra": shot_extra,
        "production": production,
        "subtitle_text": (shot_extra.get("subtitle_text") or shot.dialogue or "").strip(),
        "duration": float(request.duration_seconds or shot.duration or 4),
        "asset_locks": asset_locks,
        "asset_snapshot": snapshot.get("asset_version_locks") or asset_locks,
        "voice_snapshot": snapshot.get("voice_lock_snapshot"),
    }


def _build_media_job(
    context: WorkflowMediaContext,
    request: WorkflowMediaBatchRequest,
    state: _BatchState,
    shot: Shot,
    values: dict,
) -> MediaGenerationJob:
    workflow, model = context.workflow, state.runtime_model
    job_id, duration = str(uuid4()), values["duration"]
    artifacts = deterministic_media_provider_artifacts(
        job_id, duration_seconds=duration, include_audio=request.audio_mode != "none",
    ) if deterministic_provider_fake_enabled() else None
    production = values["production"]
    values["model_test_status"] = model.get("test_status")
    return MediaGenerationJob(
        id=job_id, user_id=context.user_id, project_id=values["extra"].get("project_id"),
        workflow_id=workflow.id, task_id=f"dev-media-{job_id}", task_type="shot_audio_video",
        media_type="audio_video", title=f"镜头{shot.shot_number} 音视频草稿",
        prompt=shot.prompt or shot.visual_description or values["subtitle_text"] or f"镜头{shot.shot_number}",
        provider_id=model.get("provider_id"), model_id=model.get("model_id"),
        model_name=model.get("model_name"), capabilities=model.get("capabilities") or [],
        novel_id=workflow.novel_id, chapter_id=workflow.chapter_id, script_id=workflow.script_id,
        storyboard_id=workflow.storyboard_id or shot.storyboard_id, shot_id=shot.id,
        duration_seconds=duration, resolution=request.resolution, input_assets=values["asset_locks"],
        output_video_url=(artifacts or {}).get("video_url") or dev_video_url(job_id, duration_seconds=duration),
        output_audio_url=((artifacts or {}).get("audio_url") if artifacts is not None
                          else dev_audio_url(job_id) if request.audio_mode != "none" else None),
        status="succeeded", progress=100, quality_report={"mode": "dev_placeholder"},
        extra_data=_job_extra(context, request, shot, values, artifacts, job_id),
    )


def _job_extra(
    context: WorkflowMediaContext,
    request: WorkflowMediaBatchRequest,
    shot: Shot,
    values: dict,
    artifacts: Optional[dict],
    job_id: str,
) -> dict:
    production = values["production"]
    return {
        "artifact_id": job_id, "episode_number": production.get("episode_number"),
        "episode_contract_version": production.get("episode_contract_version"),
        "canonical_reference_id": production.get("canonical_reference_id"),
        "canonical_reference_version": production.get("canonical_reference_version"),
        "as_of_chapter_id": production.get("as_of_chapter_id"),
        "as_of_chapter_hash": production.get("as_of_chapter_hash"),
        "artifact_completed_at": utc_now().isoformat(), "subtitle_text": values["subtitle_text"],
        "subtitle_mode": request.subtitle_mode, "audio_mode": request.audio_mode,
        **production_strategy_job_extra(request.production_strategy, context.effective_video_config_id),
        "model_config_id": context.effective_video_config_id,
        "model_test_status": values["model_test_status"],
        "strategy_routing": context.strategy_video_routing["routing"],
        "strategy_matched_api_model_id": context.strategy_video_routing["matched_api_model_id"],
        "asset_version_locks": values["asset_snapshot"], "asset_lock_snapshot": values["asset_snapshot"],
        "voice_lock_snapshot": values["voice_snapshot"], "voice_lock": values["voice_snapshot"],
        "keyframes": shot.keyframes or production.get("keyframes") or [],
        "character_multiview_refs": production.get("character_multiview_refs")
        if isinstance(production.get("character_multiview_refs"), list) else [],
        "production_contract": production.get("production_contract"),
        "lineage": _lineage(context, shot), "provider_calls": (artifacts or {}).get("provider_calls") or [],
        "deterministic_provider_fake": artifacts is not None,
    }


def _lineage(context: WorkflowMediaContext, shot: Shot) -> dict:
    workflow = context.workflow
    return {
        "workflow_id": workflow.id, "novel_id": workflow.novel_id,
        "chapter_id": workflow.chapter_id, "script_id": workflow.script_id,
        "storyboard_id": workflow.storyboard_id or shot.storyboard_id,
        "shot_id": shot.id, "shot_number": shot.shot_number,
    }


def _add_subtitles(
    context: WorkflowMediaContext, request: WorkflowMediaBatchRequest,
    state: _BatchState, shot: Shot, job: MediaGenerationJob, values: dict,
) -> None:
    if not values["subtitle_text"] or request.subtitle_mode == "off":
        return
    workflow, track_id = context.workflow, str(uuid4())
    track = SubtitleTrack(
        id=track_id, user_id=context.user_id, project_id=job.project_id, workflow_id=workflow.id,
        novel_id=workflow.novel_id, chapter_id=workflow.chapter_id, script_id=workflow.script_id,
        storyboard_id=workflow.storyboard_id or shot.storyboard_id, shot_id=shot.id,
        media_job_id=job.id, title=f"镜头{shot.shot_number} 字幕", language="zh-CN",
        kind="dialogue", source="direct_av_model", status="draft", metadata_={"media_job_id": job.id},
    )
    segment = SubtitleSegment(
        id=str(uuid4()), track_id=track.id, user_id=context.user_id, shot_id=shot.id,
        start_seconds=0.0, end_seconds=values["duration"], text=values["subtitle_text"],
        original_text=values["subtitle_text"], source="direct_av_model", confidence=1.0,
        review_status="pending_review", sort_order=1,
    )
    job.subtitle_track_id = track.id
    context.db.add(track)
    context.db.add(segment)
    state.subtitle_track_ids.append(track.id)


def _update_shot(shot: Shot, job: MediaGenerationJob, values: dict) -> None:
    shot.video_url, shot.video_status = job.output_video_url, "succeeded"
    if job.output_audio_url:
        shot.audio_url, shot.audio_status = job.output_audio_url, "succeeded"
    shot.extra_data = {
        **values["extra"], "latest_media_job_id": job.id,
        "latest_subtitle_track_id": job.subtitle_track_id,
    }


def _update_workflow(command: DirectAvCommand, state: _BatchState) -> None:
    context, request, workflow = command.context, command.request, command.context.workflow
    metadata = workflow.metadata_ if isinstance(workflow.metadata_, dict) else {}
    workflow.metadata_ = {
        **merge_latest_production_strategy(metadata, request.production_strategy),
        "media_job_ids": list(dict.fromkeys((metadata.get("media_job_ids") or []) + state.media_job_ids)),
        "subtitle_track_ids": list(dict.fromkeys(
            (metadata.get("subtitle_track_ids") or []) + state.subtitle_track_ids
        )),
        "latest_media_batch_strategy": request.strategy,
        "latest_media_batch_count": len(state.media_job_ids),
        "latest_media_batch_model_config_id": context.effective_video_config_id,
    }
    workflow.current_step = max(workflow.current_step, 7)
    workflow.completed_steps = complete_steps(workflow.completed_steps, 7, 8)


async def generate_direct_av_batch(command: DirectAvCommand) -> WorkflowMediaBatchResponse:
    context, request = command.context, command.request
    if request.require_real_video and not deterministic_provider_fake_enabled():
        raise WorkflowMediaError(422, "直生音视频真实供应商适配尚未配置；请改用视频+声音分步生成策略")
    if not is_dev_mode() and not deterministic_provider_fake_enabled():
        raise WorkflowMediaError(422, "批量直生音视频真实供应商适配尚未配置；请改用视频+声音分步生成策略")
    state = _BatchState(
        media_job_ids=[], subtitle_track_ids=[],
        lock_snapshots=await _load_lock_snapshots(context, request),
        runtime_model=await _resolve_runtime_model(context),
    )
    for shot in context.shots:
        values = _shot_inputs(shot, request, state.lock_snapshots)
        job = _build_media_job(context, request, state, shot, values)
        context.db.add(job)
        _add_subtitles(context, request, state, shot, job, values)
        _update_shot(shot, job, values)
        state.media_job_ids.append(job.id)
    _update_workflow(command, state)
    await context.db.commit()
    return WorkflowMediaBatchResponse(
        workflow_id=context.workflow.id, strategy=request.strategy,
        production_strategy=request.production_strategy, created_count=len(state.media_job_ids),
        video_job_ids=[], tts_job_ids=[], tts_voice_lock_count=0,
        media_job_ids=state.media_job_ids, subtitle_track_ids=state.subtitle_track_ids,
        pending_video_job_ids=[], pending_tts_job_ids=[], ready_for_concatenate=True,
        message="音视频草稿已生成",
    )
