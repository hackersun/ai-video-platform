"""Submit and construct TTS jobs for separate workflow-media generation."""

from dataclasses import dataclass, replace
from typing import Any, Dict, Optional
from uuid import uuid4

from app.core.dev_generation import dev_audio_url, is_dev_mode
from app.features.workflow_media.application.load_context import WorkflowMediaContext
from app.features.workflow_media.application.prepare_separate_media import PreparedSeparateMedia
from app.features.workflow_media.application.voice_locks import (
    WorkflowVoiceCommand,
    provider_compatible_tts_voice,
    resolve_workflow_tts_voice,
    uses_legacy_subtitle_only,
)
from app.features.workflow_media.domain.production_strategy import production_strategy_job_extra
from app.features.workflow_media.errors import WorkflowMediaError
from app.features.workflow_media.schemas import WorkflowMediaBatchRequest
from app.models import Shot, TTSJob
from app.services.audio_route_service import resolve_shot_audio_route
from app.services.live_canary_budget import (
    bind_provider_operation_for_reservation,
    settle_synchronous_provider_operation,
)
from app.features.workflow_media.application.live_provider_attempts import (
    finish_live_provider_attempt,
    prepare_live_provider_attempt,
)
from app.features.workflow_media.application.reference_packages import workflow_shot_lineage
from app.features.model_drivers.public import (
    DriverError,
    SpeechCommand,
    build_builtin_driver_registry,
    execute_generation,
)
from app.features.model_config.public import ExecutionSnapshotCommand, create_execution_snapshot
from app.services.minimax_errors import MiniMaxProviderRejected


@dataclass(frozen=True)
class TTSSubmissionCommand:
    context: WorkflowMediaContext
    request: WorkflowMediaBatchRequest
    preparation: PreparedSeparateMedia
    shot: Shot


@dataclass(frozen=True)
class TTSSubmissionResult:
    tts_job: Optional[TTSJob]
    voice_lock_count_delta: int
    audio_route: Dict[str, Any]
    dialogue_sync_contract: Optional[Dict[str, Any]]


@dataclass(frozen=True)
class _VoiceInputs:
    resolved: Dict[str, Any]
    lock_snapshot: Optional[Dict[str, Any]]
    lock_count_delta: int
    audio_route: Dict[str, Any]
    dialogue_contract: Optional[Dict[str, Any]]


@dataclass(frozen=True)
class _ProviderResult:
    task_id: Optional[str]
    audio_url: Optional[str]
    duration: float
    status: str
    progress: int
    reservation_id: Optional[str]


def _tts_provider_rejection_detail(error: MiniMaxProviderRejected) -> dict:
    return {
        "code": "tts_provider_rejected",
        "title": "声音生成未受理",
        "message": "当前声线无法用于所选 MiniMax 声音模型，请修改声线并重新测试后，仅重试声音阶段。",
        "stage": "tts_submission",
        "provider_status_code": error.status_code,
        "operation_status": "confirmed_rejected_before_acceptance",
        "cost_state": "released",
        "safe_retry": True,
        "retry_requires_confirmation": True,
        "retry_scope": "failed_stage",
        "actions": [
            {"code": "edit_voice", "label": "修改声线"},
            {"code": "retest_config", "label": "重新测试声音配置"},
            {"code": "retry_failed_stage", "label": "仅重试声音阶段"},
        ],
    }


def _extra(shot: Shot) -> dict:
    return shot.extra_data if isinstance(shot.extra_data, dict) else {}


def _default_voice_lock(command: TTSSubmissionCommand) -> Optional[dict]:
    snapshot = command.preparation.final_quality_snapshots.get(command.shot.id) or {}
    lock = snapshot.get("voice_lock_snapshot")
    return lock if isinstance(lock, dict) else None


def _apply_default_lock(resolved: dict, lock: Optional[dict]) -> dict:
    voice_source = resolved.get("voice_source")
    if not lock or (voice_source and voice_source != "request"):
        return resolved
    resolved.update({
        "voice": lock.get("voice") or resolved.get("voice"),
        "speed": lock.get("speed") or resolved.get("speed"),
        "voice_source": lock.get("voice_source") or "provider_default_tts",
        "character_name": lock.get("character_name") or resolved.get("character_name"),
        "story_bible_id": lock.get("story_bible_id") or resolved.get("story_bible_id"),
        "voice_asset_id": lock.get("voice_asset_id"),
        "voice_provider": lock.get("voice_provider"),
        "voice_sample_audio_url": lock.get("voice_sample_audio_url"),
    })
    return resolved


def _build_voice_lock(resolved: dict) -> tuple[Optional[dict], int]:
    source = resolved.get("voice_source")
    if not source or source == "request":
        return None, 0
    lock = {
        "character_name": resolved.get("character_name"),
        "story_bible_id": resolved.get("story_bible_id"),
        "voice": resolved.get("voice"),
        "voice_source": source,
    }
    for name in ("speed", "voice_asset_id", "voice_provider", "voice_sample_audio_url"):
        if resolved.get(name) is not None:
            lock[name] = resolved.get(name)
    return lock, 1


def _enrich_dialogue_contract(
    contract: Optional[dict], resolved: dict, voice_lock: Optional[dict],
) -> Optional[dict]:
    if not contract:
        return None
    enriched = dict(contract)
    enriched["speaker"] = enriched.get("speaker") or resolved.get("character_name")
    enriched["voice"] = resolved.get("voice")
    enriched["voice_source"] = resolved.get("voice_source")
    enriched["story_bible_id"] = resolved.get("story_bible_id")
    enriched["voice_lock_snapshot"] = voice_lock
    return enriched


async def _resolve_voice(command: TTSSubmissionCommand, prepared: dict) -> _VoiceInputs:
    context, request, shot = command.context, command.request, command.shot
    resolved = await resolve_workflow_tts_voice(WorkflowVoiceCommand(
        context.db, context.user_id, context.workflow, shot, prepared["subtitle_text"],
        request.voice_model, request.speed,
        requested_story_bible_id=request.story_bible_id,
        use_story_bible_voice=request.use_story_bible_voice,
    ))
    resolved = _apply_default_lock(resolved, _default_voice_lock(command))
    if uses_legacy_subtitle_only(shot) and resolved.get("voice_source") == "provider_default_tts":
        resolved["voice_source"] = "request"
    lock, increment = _build_voice_lock(resolved)
    dialogue = _enrich_dialogue_contract(prepared.get("dialogue_sync_contract"), resolved, lock)
    route = resolve_shot_audio_route(
        shot, model_limits=command.preparation.video_reference_limits, voice_lock=lock,
    )
    return _VoiceInputs(resolved, lock, increment, route, dialogue)


async def _call_provider(
    command: TTSSubmissionCommand, text: str, voice: str, speed: float,
    execution_snapshot_id: str | None = None,
) -> dict:
    model = command.preparation.selected_audio_model or {}
    generation = model.get("generation_context")
    if generation is not None:
        try:
            submission = await execute_generation(
                build_builtin_driver_registry(),
                SpeechCommand(
                    text=text,
                    voice_id=voice,
                    params={**dict(generation.profile.default_params), "speed": speed},
                ),
                replace(generation.driver_context, execution_snapshot_id=execution_snapshot_id)
                if execution_snapshot_id else generation.driver_context,
            )
        except DriverError as error:
            raise WorkflowMediaError(422, str(error)) from error
        result = dict(submission.output)
        if submission.provider_task_id and not result.get("task_id"):
            result["task_id"] = submission.provider_task_id
        return result
    api_key = command.preparation.audio_api_key
    if model.get("provider_id") == "minimax":
        from app.services.minimax_service import MiniMaxService

        return await MiniMaxService(api_key, model.get("base_url")).text_to_speech(
            text=text, model=model.get("model_id") or "speech-2.6-hd", voice_id=voice, speed=speed,
        )
    if model.get("provider_id") == "volcano":
        from app.services.volcano_service import VolcanoService

        return await VolcanoService(api_key, model.get("base_url")).text_to_speech(
            text=text, model=model.get("model_id") or "doubao-tts", voice=voice, speed=speed,
        )
    raise WorkflowMediaError(
        422, f"批量声音生成暂不支持 {model.get('provider_id')}，请改用 MiniMax 或火山 TTS 模型",
    )


async def _live_provider_result(
    command: TTSSubmissionCommand, job_id: str, text: str, voice: str, speed: float,
    execution_snapshot_id: str | None = None,
) -> _ProviderResult:
    context, shot = command.context, command.shot
    reservation = await prepare_live_provider_attempt(
        context.db, context.series_run, capability="tts",
        reservation_id=f"{context.workflow.id}:{shot.id}:tts:{uuid4()}",
        job_type="tts_job", job_id=job_id,
    )
    try:
        result = await _call_provider(command, text, voice, speed, execution_snapshot_id)
    except MiniMaxProviderRejected as error:
        await finish_live_provider_attempt(
            context.db, context.series_run, reservation, submission_failed=True,
        )
        raise WorkflowMediaError(422, _tts_provider_rejection_detail(error)) from error
    task_id = result.get("task_id")
    if reservation and not task_id and result.get("audio_url"):
        operation_id = context.series_run.cost_summary["reservations"][reservation].get("operation_id")
        task_id = f"sync:{operation_id}"
    operation = None
    if reservation and task_id:
        operation = await bind_provider_operation_for_reservation(
            context.db, context.series_run, reservation_id=reservation, provider_task_id=task_id,
        )
    audio_url = result.get("audio_url")
    duration = result.get("duration")
    status = "succeeded" if audio_url else result.get("status", "pending")
    if operation and status in {"succeeded", "completed"}:
        await settle_synchronous_provider_operation(
            context.db, operation,
            provider_actual_rmb=result.get("actual_cost_rmb", result.get("cost_rmb")),
        )
    return _ProviderResult(
        task_id, audio_url, duration, status,
        100 if status in {"succeeded", "completed"} else 20, reservation,
    )


async def _submit_provider(
    command: TTSSubmissionCommand, job_id: str, text: str, voice: str, speed: float, duration: float,
    execution_snapshot_id: str | None = None,
) -> _ProviderResult:
    if command.preparation.audio_api_key:
        result = await _live_provider_result(command, job_id, text, voice, speed, execution_snapshot_id)
        return _ProviderResult(
            result.task_id, result.audio_url, result.duration or duration,
            result.status, result.progress, result.reservation_id,
        )
    use_dev = is_dev_mode()
    return _ProviderResult(
        f"dev-tts-{job_id}" if use_dev else None,
        dev_audio_url(job_id) if use_dev else None,
        duration, "succeeded" if use_dev else "pending", 100 if use_dev else 10, None,
    )


def _generation_preflight(prepared: dict) -> Optional[dict]:
    package = prepared.get("tts_preflight_package")
    if package is None:
        return None
    return {
        "ready": package.get("ready"), "issues": package.get("issues") or [],
        "blocking_issue_count": package.get("blocking_issue_count") or 0,
    }


def _job_extra(
    command: TTSSubmissionCommand, prepared: dict, voice: _VoiceInputs,
    execution_snapshot_id: str | None = None,
) -> dict:
    request, model = command.request, command.preparation.selected_audio_model
    resolved = voice.resolved
    extra = {
        "model_config_id": request.audio_model_config_id,
        "api_model_id": model.get("model_id") if model else None,
        "provider_id": model.get("provider_id") if model else None,
        "model_test_status": model.get("test_status") if model else None,
        **production_strategy_job_extra(request.production_strategy, request.audio_model_config_id),
        "generation_strategy": request.strategy, "audio_route": voice.audio_route,
        "generation_preflight": _generation_preflight(prepared),
        "voice_source": resolved.get("voice_source"),
        "voice_character_name": resolved.get("character_name"),
        "story_bible_id": resolved.get("story_bible_id"),
        "voice_lock": voice.lock_snapshot, "voice_lock_snapshot": voice.lock_snapshot,
        "dialogue_sync_contract": voice.dialogue_contract,
        "lineage": {
            **workflow_shot_lineage(command.context.workflow, command.shot),
            "story_bible_id": resolved.get("story_bible_id"),
        },
    }
    if execution_snapshot_id:
        extra["execution_snapshot_id"] = execution_snapshot_id
    return extra


def _add_live_accounting(
    command: TTSSubmissionCommand, extra: dict, provider: _ProviderResult,
) -> dict:
    if not provider.reservation_id:
        return extra
    run = command.context.series_run
    reservation = run.cost_summary["reservations"][provider.reservation_id]
    return {**extra, "live_canary_accounting": {
        "series_run_id": run.id, "reservation_id": provider.reservation_id,
        "provider_task_id": provider.task_id, "capability": "tts",
        "operation_id": reservation.get("operation_id"),
    }}


def _build_job(
    command: TTSSubmissionCommand, job_id: str, text: str, voice: _VoiceInputs,
    provider: _ProviderResult, tts_voice: str, execution_snapshot_id: str | None = None,
) -> TTSJob:
    context, shot, model = command.context, command.shot, command.preparation.selected_audio_model
    extra = _add_live_accounting(
        command,
        _job_extra(command, command.preparation.prepared_shots[shot.id], voice, execution_snapshot_id),
        provider,
    )
    return TTSJob(
        id=job_id, user_id=context.user_id, project_id=_extra(shot).get("project_id"),
        workflow_id=context.workflow.id, task_id=provider.task_id, title=f"镜头{shot.shot_number} 配音",
        text=text, model_id=model.get("model_id") if model else None,
        model_name=model.get("model_name") if model else None, voice=tts_voice,
        speed=float(voice.resolved.get("speed") or command.request.speed),
        api_provider=model.get("provider_id") if model else None,
        novel_id=context.workflow.novel_id, chapter_id=context.workflow.chapter_id,
        script_id=context.workflow.script_id,
        storyboard_id=context.workflow.storyboard_id or shot.storyboard_id, shot_id=shot.id,
        status=provider.status, progress=provider.progress, audio_url=provider.audio_url,
        duration_seconds=provider.duration if provider.audio_url else None, extra_data=extra,
    )


async def _create_execution_snapshot(
    command: TTSSubmissionCommand, job_id: str, voice: str, speed: float,
) -> str | None:
    model = command.preparation.selected_audio_model or {}
    generation = model.get("generation_context")
    if generation is None:
        return None
    snapshot = await create_execution_snapshot(
        command.context.db,
        ExecutionSnapshotCommand(
            user_id=command.context.user_id,
            run_id=getattr(command.context.series_run, "id", None),
            job_id=job_id,
            task=generation.binding.task,
            capability=generation.binding.capability,
            binding=generation.binding,
            sanitized_params={"voice_id": voice, "speed": speed},
        ),
    )
    return snapshot.id


async def submit_tts_for_shot(command: TTSSubmissionCommand) -> TTSSubmissionResult:
    prepared = command.preparation.prepared_shots[command.shot.id]
    route, subtitle = dict(prepared["audio_route"]), prepared["subtitle_text"]
    if command.request.audio_mode == "none" or route.get("route") != "tts" or not subtitle:
        return TTSSubmissionResult(None, 0, route, prepared.get("dialogue_sync_contract"))
    voice = await _resolve_voice(command, prepared)
    model = command.preparation.selected_audio_model
    tts_voice = str(provider_compatible_tts_voice(
        voice.resolved.get("voice") or command.request.voice_model, model,
    ))
    speed = float(voice.resolved.get("speed") or command.request.speed)
    text = (str(voice.dialogue_contract.get("spoken_text") or "").strip()
            if voice.dialogue_contract else subtitle) or subtitle
    duration = max(1.0, min(prepared["duration"], len(text) / 4.0 / max(speed, 0.1)))
    job_id = str(uuid4())
    execution_snapshot_id = await _create_execution_snapshot(command, job_id, tts_voice, speed)
    provider = await _submit_provider(
        command, job_id, text, tts_voice, speed, duration, execution_snapshot_id,
    )
    job = _build_job(command, job_id, text, voice, provider, tts_voice, execution_snapshot_id)
    return TTSSubmissionResult(job, voice.lock_count_delta, voice.audio_route, voice.dialogue_contract)
