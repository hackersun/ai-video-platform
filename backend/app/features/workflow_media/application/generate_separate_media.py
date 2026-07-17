"""Coordinate prepared video/TTS submission and ordered persistence."""

from app.features.workflow_media.adapters.tts_submission import (
    TTSSubmissionCommand,
    submit_tts_for_shot,
)
from app.features.workflow_media.adapters.video_submission import (
    PreparedVideoSubmission,
    VideoSubmissionCommand,
    VideoSubmissionRuntime,
    submit_video,
)
from app.features.workflow_media.application.load_context import WorkflowMediaContext
from app.features.workflow_media.application.persist_separate_media import (
    PersistSeparateMediaCommand,
    SeparateMediaRecord,
    begin_separate_persist,
    finish_separate_media_record,
    finish_separate_persist,
    start_separate_media_record,
)
from app.features.workflow_media.application.prepare_separate_media import (
    PrepareSeparateMediaCommand,
    prepare_separate_media,
)
from app.features.workflow_media.schemas import WorkflowMediaBatchRequest, WorkflowMediaBatchResponse


def _video_input(preparation, shot) -> PreparedVideoSubmission:
    prepared = preparation.prepared_shots[shot.id]
    return PreparedVideoSubmission(
        prepared["video_request"], prepared["lineage"], prepared["package"],
        prepared["reference_package"], prepared["final_video_prompt"],
        prepared["effective_image_url"], prepared["video_seed"],
        prepared["audio_route"], prepared["dialogue_sync_contract"],
        prepared["video_preflight_package"],
        preparation.final_quality_snapshots.get(shot.id) or {},
    )


def _video_runtime(preparation) -> VideoSubmissionRuntime:
    return VideoSubmissionRuntime(
        preparation.selected_video_model, preparation.video_reference_limits,
        preparation.selected_video_model_id, preparation.selected_video_provider,
        preparation.video_api_key, preparation.use_dev_video,
    )


def _record(shot, video, tts, prepared) -> SeparateMediaRecord:
    return SeparateMediaRecord(
        shot, video.video_job, tts.tts_job if tts else None,
        video.sync_succeeded_video, prepared["subtitle_text"], prepared["duration"],
    )


async def generate_separate_media_batch(
    context: WorkflowMediaContext,
    request: WorkflowMediaBatchRequest,
) -> WorkflowMediaBatchResponse:
    preparation = await prepare_separate_media(PrepareSeparateMediaCommand(context, request))
    persist_command = PersistSeparateMediaCommand(context, request, [], 0)
    session = begin_separate_persist(persist_command)
    runtime = _video_runtime(preparation)
    for shot in context.shots:
        tts = None if getattr(request, "native_audio", False) else await submit_tts_for_shot(
            TTSSubmissionCommand(context, request, preparation, shot)
        )
        video = await submit_video(VideoSubmissionCommand(
            context, request, shot, _video_input(preparation, shot), runtime,
        ))
        prepared = preparation.prepared_shots[shot.id]
        if tts is not None and tts.tts_job is not None:
            video.video_job.extra_data = {
                **(video.video_job.extra_data or {}),
                "audio_route": tts.audio_route,
                "dialogue_sync_contract": tts.dialogue_sync_contract,
            }
        await start_separate_media_record(session, _record(shot, video, tts, prepared))
        session.tts_voice_lock_count += tts.voice_lock_count_delta if tts is not None else 0
        finish_separate_media_record(session, _record(shot, video, tts, prepared))
    return await finish_separate_persist(session)
