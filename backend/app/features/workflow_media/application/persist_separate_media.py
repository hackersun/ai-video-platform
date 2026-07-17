"""Persist prepared separate-video-and-TTS workflow media records."""

from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from app.features.video_generation.public import VideoJobSyncCommand, sync_video_job_and_shot
from app.features.workflow_media.application.load_context import WorkflowMediaContext
from app.features.workflow_media.domain.production_strategy import merge_latest_production_strategy
from app.features.workflow_media.domain.workflow_state import complete_steps
from app.features.workflow_media.errors import WorkflowMediaError
from app.features.workflow_media.schemas import WorkflowMediaBatchRequest, WorkflowMediaBatchResponse
from app.models import Shot, TTSJob, VideoJob
from app.models.subtitle import SubtitleSegment, SubtitleTrack


@dataclass(frozen=True)
class SeparateMediaRecord:
    """Provider-prepared persistence input for one workflow shot."""

    shot: Shot
    video_job: VideoJob
    tts_job: Optional[TTSJob]
    sync_succeeded_video: bool
    subtitle_text: str
    duration: float


@dataclass(frozen=True)
class PersistSeparateMediaCommand:
    context: WorkflowMediaContext
    request: WorkflowMediaBatchRequest
    records: list[SeparateMediaRecord]
    tts_voice_lock_count: int


@dataclass
class _PersistState:
    video_job_ids: list[str]
    tts_job_ids: list[str]
    subtitle_track_ids: list[str]
    pending_video_job_ids: list[str]
    pending_tts_job_ids: list[str]


@dataclass
class SeparatePersistSession:
    command: PersistSeparateMediaCommand
    state: _PersistState
    tts_voice_lock_count: int = 0


def _new_state() -> _PersistState:
    return _PersistState([], [], [], [], [])


def _validate(command: PersistSeparateMediaCommand) -> None:
    if command.request.strategy != "separate_video_tts":
        raise WorkflowMediaError(422, "持久化命令仅支持 separate_video_tts 策略")
    expected = [shot.id for shot in command.context.shots]
    actual = [record.shot.id for record in command.records]
    if actual != expected:
        raise WorkflowMediaError(422, "分步媒体持久化记录必须与工作流镜头顺序一致")


def _add_subtitle(
    command: PersistSeparateMediaCommand,
    record: SeparateMediaRecord,
) -> Optional[str]:
    if not record.subtitle_text or command.request.subtitle_mode == "off":
        return None
    context, workflow, shot = command.context, command.context.workflow, record.shot
    native_audio = bool(getattr(command.request, "native_audio", False))
    track = SubtitleTrack(
        id=str(uuid4()), user_id=context.user_id, workflow_id=workflow.id,
        novel_id=workflow.novel_id, chapter_id=workflow.chapter_id,
        script_id=workflow.script_id, storyboard_id=workflow.storyboard_id or shot.storyboard_id,
        shot_id=shot.id, media_job_id=record.video_job.id,
        title=f"镜头{shot.shot_number} 字幕", language="zh-CN", kind="dialogue",
        source="video_native_audio" if native_audio else "separate_video_tts", status="draft",
        metadata_={"media_job_id": record.video_job.id},
    )
    segment = SubtitleSegment(
        id=str(uuid4()), track_id=track.id, user_id=context.user_id, shot_id=shot.id,
        start_seconds=0.0, end_seconds=record.duration, text=record.subtitle_text,
        original_text=record.subtitle_text,
        source="video_native_audio" if native_audio else "separate_video_tts", confidence=1.0,
        review_status="pending_review", sort_order=1,
    )
    context.db.add(track)
    context.db.add(segment)
    return track.id


async def start_separate_media_record(
    session: SeparatePersistSession,
    record: SeparateMediaRecord,
) -> None:
    command, state = session.command, session.state
    expected = command.context.shots[len(state.video_job_ids)]
    if record.shot.id != expected.id:
        raise WorkflowMediaError(422, "分步媒体持久化记录必须与工作流镜头顺序一致")
    db, video_job = command.context.db, record.video_job
    db.add(video_job)
    state.video_job_ids.append(video_job.id)
    if video_job.status not in {"succeeded", "completed"}:
        state.pending_video_job_ids.append(video_job.id)
    if record.sync_succeeded_video:
        await sync_video_job_and_shot(db, video_job, VideoJobSyncCommand(
            "succeeded", 100, video_job.video_url, video_job.cover_url,
        ))


def finish_separate_media_record(
    session: SeparatePersistSession,
    record: SeparateMediaRecord,
) -> None:
    command, state = session.command, session.state
    db, shot = command.context.db, record.shot
    tts_job_id = None
    if record.tts_job is not None:
        tts_job = record.tts_job
        db.add(tts_job)
        state.tts_job_ids.append(tts_job.id)
        tts_job_id = tts_job.id
        if tts_job.status not in {"succeeded", "completed"}:
            state.pending_tts_job_ids.append(tts_job.id)
        if tts_job.audio_url:
            shot.audio_url, shot.audio_status = tts_job.audio_url, tts_job.status

    track_id = _add_subtitle(command, record)
    if track_id:
        state.subtitle_track_ids.append(track_id)
    shot_extra = shot.extra_data if isinstance(shot.extra_data, dict) else {}
    shot.extra_data = {
        **shot_extra,
        "latest_video_job_id": record.video_job.id,
        "latest_tts_job_id": tts_job_id,
        "latest_subtitle_track_id": (
            state.subtitle_track_ids[-1]
            if state.subtitle_track_ids else shot_extra.get("latest_subtitle_track_id")
        ),
    }


def begin_separate_persist(
    command: PersistSeparateMediaCommand,
) -> SeparatePersistSession:
    if command.request.strategy != "separate_video_tts":
        raise WorkflowMediaError(422, "持久化命令仅支持 separate_video_tts 策略")
    return SeparatePersistSession(command, _new_state(), command.tts_voice_lock_count)


def _update_workflow(command: PersistSeparateMediaCommand, state: _PersistState) -> None:
    context, request, workflow = command.context, command.request, command.context.workflow
    workflow.video_job_ids = list(dict.fromkeys((workflow.video_job_ids or []) + state.video_job_ids))
    workflow.tts_job_ids = list(dict.fromkeys((workflow.tts_job_ids or []) + state.tts_job_ids))
    metadata = workflow.metadata_ if isinstance(workflow.metadata_, dict) else {}
    workflow.metadata_ = {
        **merge_latest_production_strategy(metadata, request.production_strategy),
        "subtitle_track_ids": list(dict.fromkeys(
            (metadata.get("subtitle_track_ids") or []) + state.subtitle_track_ids
        )),
        "latest_media_batch_strategy": request.strategy,
        "latest_media_batch_count": len(state.video_job_ids),
        "latest_media_batch_model_config_id": context.effective_video_config_id,
        "latest_media_batch_audio_model_config_id": request.audio_model_config_id,
        "latest_video_job_ids": state.video_job_ids,
        "latest_tts_job_ids": state.tts_job_ids,
    }
    workflow.current_step = max(workflow.current_step, 8)
    workflow.completed_steps = complete_steps(workflow.completed_steps, 7, 8)


async def persist_separate_media_batch(
    command: PersistSeparateMediaCommand,
) -> WorkflowMediaBatchResponse:
    """Persist prepared jobs and return the existing batch response contract."""
    _validate(command)
    session = begin_separate_persist(command)
    for record in command.records:
        await start_separate_media_record(session, record)
        finish_separate_media_record(session, record)
    return await finish_separate_persist(session)


async def finish_separate_persist(
    session: SeparatePersistSession,
) -> WorkflowMediaBatchResponse:
    command, state = session.command, session.state
    native_audio = bool(getattr(command.request, "native_audio", False))
    _update_workflow(command, state)
    await command.context.db.commit()
    ready = not state.pending_video_job_ids and not state.pending_tts_job_ids
    return WorkflowMediaBatchResponse(
        workflow_id=command.context.workflow.id, strategy=command.request.strategy,
        production_strategy=command.request.production_strategy,
        created_count=len(state.video_job_ids), video_job_ids=state.video_job_ids,
        tts_job_ids=state.tts_job_ids, tts_voice_lock_count=session.tts_voice_lock_count,
        media_job_ids=[], subtitle_track_ids=state.subtitle_track_ids,
        pending_video_job_ids=state.pending_video_job_ids,
        pending_tts_job_ids=state.pending_tts_job_ids, ready_for_concatenate=ready,
        message=(("原生有声视频任务已创建" if ready else "原生有声视频任务已提交，需等待生成完成")
                 if native_audio else
                 ("视频和声音任务已创建" if ready else "视频/声音任务已提交，需等待任务完成后再合成")),
    )
