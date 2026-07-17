"""Reconcile separate provider jobs into truthful selected-anchor artifacts."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models import MediaGenerationJob, Shot, SubtitleTrack, TTSJob, VideoJob, Workflow
from app.models.subtitle import SubtitleSegment
from app.models.live_canary_provider_operation import LiveCanaryProviderOperation
from app.models.series_anchor_generation_submission import SeriesAnchorGenerationSubmission
from app.models.series_production_run import SeriesProductionRun
from app.services.media_delivery import resolve_provider_media_url
from app.services.native_audio_subtitle_renderer import (
    NativeAudioSubtitleRenderError,
    burn_native_audio_subtitles,
)

from .errors import SeriesAnchorError
from .quality_status import unevaluated_quality_results


TERMINAL_SUCCESS = {"succeeded", "completed"}
TERMINAL_FAILURE = {"failed", "cancelled", "archived"}


@dataclass(frozen=True)
class _Sources:
    videos: list[VideoJob]
    voices: list[TTSJob]
    video_ids: list[str]
    tts_ids: list[str]


def _ids(batches: list[dict], key: str) -> list[str]:
    return list(dict.fromkeys(str(value) for batch in batches for value in batch.get(key) or []))


def pending_source_response(selected: list[str], batches: list[dict]) -> dict | None:
    video_ids, tts_ids = _ids(batches, "video_job_ids"), _ids(batches, "tts_job_ids")
    if not video_ids and not tts_ids:
        return None
    pending_video = _ids(batches, "pending_video_job_ids")
    pending_tts = _ids(batches, "pending_tts_job_ids")
    return {
        "status": "provider_pending" if pending_video or pending_tts else "provider_ready",
        "selected_shot_ids": selected, "workflow_batches": batches, "quality_results": [],
        "video_job_ids": video_ids, "tts_job_ids": tts_ids,
        "pending_video_job_ids": pending_video, "pending_tts_job_ids": pending_tts,
    }


async def _owned_context(
    db: AsyncSession, run_id: str, user_id: str,
) -> tuple[SeriesProductionRun, SeriesAnchorGenerationSubmission]:
    run = await db.scalar(select(SeriesProductionRun).where(
        SeriesProductionRun.id == run_id, SeriesProductionRun.user_id == user_id,
    ))
    if run is None:
        raise SeriesAnchorError(404, "series run not found")
    submission = await db.scalar(select(SeriesAnchorGenerationSubmission).where(
        SeriesAnchorGenerationSubmission.run_id == run_id,
        SeriesAnchorGenerationSubmission.user_id == user_id,
    ).order_by(SeriesAnchorGenerationSubmission.created_at.desc()).limit(1))
    if submission is None:
        raise SeriesAnchorError(409, {"code": "generation_submission_missing", "message": "尚未提交关键镜头生成"})
    return run, submission


async def _load_sources(db: AsyncSession, user_id: str, batches: list[dict]) -> _Sources:
    video_ids, tts_ids = _ids(batches, "video_job_ids"), _ids(batches, "tts_job_ids")
    videos = list((await db.scalars(select(VideoJob).where(
        VideoJob.id.in_(video_ids), VideoJob.user_id == user_id, VideoJob.is_active.is_(True),
    ))).all()) if video_ids else []
    voices = list((await db.scalars(select(TTSJob).where(
        TTSJob.id.in_(tts_ids), TTSJob.user_id == user_id, TTSJob.is_active.is_(True),
    ))).all()) if tts_ids else []
    if len(videos) != len(video_ids) or len(voices) != len(tts_ids):
        raise SeriesAnchorError(409, {
            "code": "provider_source_job_missing", "message": "关键镜头源任务缺失或不属于当前用户",
        })
    return _Sources(videos, voices, video_ids, tts_ids)


def _terminal_response(submission: SeriesAnchorGenerationSubmission, sources: _Sources) -> dict | None:
    failed_video = [job.id for job in sources.videos if job.status in TERMINAL_FAILURE]
    failed_tts = [job.id for job in sources.voices if job.status in TERMINAL_FAILURE]
    payload = dict(submission.response_payload or {})
    if failed_video or failed_tts:
        return {**payload, "status": "failed", "failed_video_job_ids": failed_video,
                "failed_tts_job_ids": failed_tts, "pending_video_job_ids": [], "pending_tts_job_ids": []}
    pending_video = [job.id for job in sources.videos if job.status not in TERMINAL_SUCCESS]
    pending_tts = [job.id for job in sources.voices if job.status not in TERMINAL_SUCCESS]
    if pending_video or pending_tts:
        return {**payload, "status": "provider_pending", "pending_video_job_ids": pending_video,
                "pending_tts_job_ids": pending_tts}
    return None


def _shot_id(job: VideoJob) -> str:
    extra = job.extra_data if isinstance(job.extra_data, dict) else {}
    lineage = extra.get("lineage") if isinstance(extra.get("lineage"), dict) else {}
    return str(lineage.get("shot_id") or extra.get("shot_id") or "")


async def _provider_calls(
    db: AsyncSession, run: SeriesProductionRun, video: VideoJob, voice: TTSJob | None,
) -> list[dict]:
    operations = list((await db.scalars(select(LiveCanaryProviderOperation).where(
        LiveCanaryProviderOperation.run_id == run.id,
    ))).all())
    reference_id = str(((run.run_metadata or {}).get("reference_preparation") or {}).get("asset_id") or "")
    selected = []
    for capability, job_id in (("reference", reference_id), ("video", video.id), ("tts", voice.id if voice else "")):
        if not job_id:
            continue
        operation = next((item for item in operations if
                          (capability == "reference" and item.artifact_id == job_id)
                          or (capability != "reference" and item.job_id == job_id)), None)
        if operation is None or not operation.provider_task_id:
            raise SeriesAnchorError(409, {"code": "provider_operation_evidence_missing",
                                          "message": f"{capability} 源任务缺少供应商操作证据"})
        selected.append({"capability": capability, "status": operation.status,
                         "provider_task_id": operation.provider_task_id, "operation_id": operation.id,
                         "actual_rmb": operation.actual_rmb, "cost_source": operation.cost_source})
    return selected


async def _finalize_native_audio_subtitles(
    db: AsyncSession, run: SeriesProductionRun, shot: Shot, video: VideoJob,
) -> SubtitleTrack | None:
    track = await db.scalar(select(SubtitleTrack).where(
        SubtitleTrack.user_id == run.user_id,
        SubtitleTrack.shot_id == shot.id,
        SubtitleTrack.is_active.is_(True),
    ).order_by(SubtitleTrack.created_at.desc()).limit(1))
    if track is None:
        return None
    segments = list((await db.scalars(select(SubtitleSegment).where(
        SubtitleSegment.track_id == track.id,
        SubtitleSegment.user_id == run.user_id,
        SubtitleSegment.is_active.is_(True),
    ).order_by(SubtitleSegment.start_seconds, SubtitleSegment.sort_order))).all())
    payload = [{
        "start_seconds": item.start_seconds,
        "end_seconds": item.end_seconds,
        "text": item.text,
    } for item in segments if str(item.text or "").strip()]
    if not payload:
        raise SeriesAnchorError(409, {
            "code": "native_audio_subtitle_missing",
            "message": "原生有声视频没有可烧录字幕，请补充字幕文本后重试聚合。",
            "shot_id": shot.id,
        })
    try:
        result = await asyncio.to_thread(burn_native_audio_subtitles, video.video_url, payload)
    except NativeAudioSubtitleRenderError as error:
        raise SeriesAnchorError(409, {
            **error.detail, "shot_id": shot.id,
            "message": f"{error.detail['message']}；修复后可直接重试聚合，不会重复调用视频模型。",
        }) from error
    original_url = video.video_url
    video.video_url = result["video_url"]
    delivery = await resolve_provider_media_url(
        db, run.user_id, video.video_url, media_type="视频",
    )
    public_url = delivery.get("provider_url")
    extra = dict(video.extra_data or {})
    video.extra_data = {
        **extra,
        "original_native_audio_video_url": original_url,
        "subtitle_burned": True,
        "subtitle_track_id": track.id,
        "subtitle_count": result["subtitle_count"],
        "subtitle_audio_preserved": result["audio_preserved"],
        "subtitle_public_video_url": public_url,
        "subtitle_delivery": {
            "method": delivery.get("delivery_method"),
            "object_key": delivery.get("object_key"),
            "omitted_reason": delivery.get("omitted_reason"),
        },
    }
    track.status = "ready"
    track.export_urls = {**(track.export_urls or {}), "burned_video": video.video_url,
                         **({"public_video": public_url} if public_url else {})}
    track.metadata_ = {**(track.metadata_ or {}), "burned": True, "audio_preserved": True}
    return track


async def _aggregate_one(
    db: AsyncSession, run: SeriesProductionRun, shot: Shot, video: VideoJob, voice: TTSJob | None,
) -> MediaGenerationJob:
    workflow = await db.get(Workflow, video.workflow_id)
    if workflow is None or workflow.user_id != run.user_id:
        raise SeriesAnchorError(409, {"code": "provider_source_lineage_invalid", "message": "源任务工作流血缘无效"})
    production = dict((shot.extra_data or {}).get("production_context") or {})
    calls = await _provider_calls(db, run, video, voice)
    job_id = str(uuid4())
    extra = video.extra_data if isinstance(video.extra_data, dict) else {}
    native_audio = bool(extra.get("video_native_audio"))
    finalized_track = await _finalize_native_audio_subtitles(db, run, shot, video) if native_audio else None
    extra = video.extra_data if isinstance(video.extra_data, dict) else {}
    aggregate = MediaGenerationJob(
        id=job_id, user_id=run.user_id, project_id=video.project_id, workflow_id=workflow.id,
        task_id=video.task_id, task_type="shot_audio_video", media_type="audio_video",
        title=f"镜头{shot.shot_number} {'原生有声' if native_audio else '实模'}音视频", prompt=video.prompt,
        provider_id=extra.get("provider_id"), model_id=video.model_id, model_name=video.model_name,
        capabilities=["video", "native_audio"] if native_audio else ["video", "tts"],
        novel_id=workflow.novel_id, chapter_id=workflow.chapter_id,
        script_id=workflow.script_id, storyboard_id=workflow.storyboard_id or shot.storyboard_id,
        shot_id=shot.id, duration_seconds=video.duration, resolution=video.resolution,
        input_assets=list(production.get("asset_version_locks") or []),
        source_job_ids={"video_job_id": video.id, "tts_job_id": voice.id if voice else None},
        output_video_url=video.video_url, output_audio_url=voice.audio_url if voice else None,
        cover_url=video.cover_url, status="succeeded", progress=100,
        quality_report={"mode": "trusted_multimodal_evaluation_required"},
        extra_data={**production, "artifact_id": job_id, "artifact_completed_at": utc_now().isoformat(),
                    "model_config_id": extra.get("model_config_id"), "provider_calls": calls,
                    "video_native_audio": native_audio,
                    "audio_source": "video_native_audio" if native_audio else "separate_tts",
                    "subtitle_burned": extra.get("subtitle_burned") is True,
                    "subtitle_public_video_url": extra.get("subtitle_public_video_url"),
                    "subtitle_delivery": extra.get("subtitle_delivery"),
                    "lineage": {"workflow_id": workflow.id, "shot_id": shot.id}},
    )
    db.add(aggregate)
    shot.video_url, shot.video_status = video.video_url, "succeeded"
    if voice:
        shot.audio_url, shot.audio_status = voice.audio_url, "succeeded"
    shot.extra_data = {**(shot.extra_data or {}), "latest_media_job_id": aggregate.id}
    metadata = dict(workflow.metadata_ or {})
    workflow.metadata_ = {**metadata, "media_job_ids": list(dict.fromkeys(
        [*(metadata.get("media_job_ids") or []), aggregate.id])), "latest_media_job_id": aggregate.id}
    track = finalized_track or await db.scalar(select(SubtitleTrack).where(
        SubtitleTrack.user_id == run.user_id, SubtitleTrack.shot_id == shot.id,
    ).order_by(SubtitleTrack.created_at.desc()).limit(1))
    if track:
        track.media_job_id, aggregate.subtitle_track_id = aggregate.id, track.id
    return aggregate


async def _aggregate_sources(
    db: AsyncSession, run: SeriesProductionRun, selected: list[str], sources: _Sources,
) -> list[MediaGenerationJob]:
    shots = list((await db.scalars(select(Shot).where(
        Shot.id.in_(selected), Shot.user_id == run.user_id,
    ))).all())
    by_shot, video_by_shot = {shot.id: shot for shot in shots}, {_shot_id(job): job for job in sources.videos}
    voice_by_shot = {str(job.shot_id): job for job in sources.voices}
    video_shots, voice_shots = set(video_by_shot), set(voice_by_shot)
    lineage_valid = (
        set(by_shot) == set(selected)
        and bool(video_shots)
        and video_shots.issubset(set(selected))
        and voice_shots.issubset(video_shots)
        and len(video_by_shot) == len(sources.videos)
        and len(voice_by_shot) == len(sources.voices)
    )
    if not lineage_valid:
        raise SeriesAnchorError(409, {"code": "provider_source_lineage_invalid",
                                      "message": "源任务与所选关键镜头血缘不一致"})
    return [await _aggregate_one(db, run, by_shot[shot_id], video_by_shot[shot_id], voice_by_shot.get(shot_id))
            for shot_id in selected if shot_id in video_by_shot]


async def _selected_aggregates(
    db: AsyncSession, *, user_id: str, selected: list[str], expected_ids: list[str],
) -> list[MediaGenerationJob]:
    jobs = list((await db.scalars(select(MediaGenerationJob).where(
        MediaGenerationJob.id.in_(expected_ids), MediaGenerationJob.user_id == user_id,
        MediaGenerationJob.is_active.is_(True), MediaGenerationJob.status.in_(TERMINAL_SUCCESS),
    ))).all())
    by_shot = {str(job.shot_id): job for job in jobs}
    if len(jobs) != len(expected_ids) or set(by_shot) != set(selected):
        raise SeriesAnchorError(409, {"code": "provider_source_lineage_invalid",
                                      "message": "新生成与复用产物未完整覆盖所选关键镜头"})
    return [by_shot[shot_id] for shot_id in selected]


async def reconcile_selected_media(db: AsyncSession, *, run_id: str, user_id: str) -> dict:
    run, submission = await _owned_context(db, run_id, user_id)
    if submission.status == "completed":
        return dict(submission.response_payload or {})
    if submission.status == "failed":
        return dict(submission.response_payload or {})
    payload = dict(submission.response_payload or {})
    batches, selected = list(payload.get("workflow_batches") or []), list(payload.get("selected_shot_ids") or [])
    sources = await _load_sources(db, user_id, batches)
    terminal = _terminal_response(submission, sources)
    if terminal is not None:
        submission.status = "failed" if terminal["status"] == "failed" else "provider_pending"
        submission.response_payload = terminal
        await db.commit()
        return terminal
    new_aggregates = await _aggregate_sources(db, run, selected, sources)
    await db.flush()
    reused_ids = _ids(batches, "media_job_ids")
    aggregates = await _selected_aggregates(
        db, user_id=user_id, selected=selected,
        expected_ids=[*reused_ids, *(job.id for job in new_aggregates)],
    )
    workflow_for_shot = {str(job.shot_id): str(job.workflow_id) for job in aggregates}
    episodes = {str((item.get("canonical_ids") or {}).get("workflow_id")): item for item in run.episodes or []}
    selected_rows_by_id = {shot.id: shot for shot in (await db.scalars(
        select(Shot).where(Shot.id.in_(selected), Shot.user_id == user_id)
    )).all()}
    selected_rows = [selected_rows_by_id[shot_id] for shot_id in selected]
    quality = await unevaluated_quality_results(
        db, user_id=user_id, selected_shots=selected_rows,
        workflow_for_shot=workflow_for_shot, episode_by_workflow=episodes,
    )
    response = {**payload, "status": "completed", "media_job_ids": [job.id for job in aggregates],
                "pending_video_job_ids": [], "pending_tts_job_ids": [], "quality_results": quality}
    submission.status, submission.response_payload = "completed", response
    await db.commit()
    return response


__all__ = ["pending_source_response", "reconcile_selected_media"]
