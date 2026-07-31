"""Submit one prepared separate-workflow video without persistence."""

import os
from dataclasses import replace
from dataclasses import dataclass
from typing import Any, Optional
from uuid import uuid4

from app.core.dev_generation import dev_video_url
from app.features.video_generation import public as video_kernel
from app.features.video_generation.schemas import VideoGenerateRequest
from app.features.model_drivers.public import (
    DriverError,
    VideoCommand,
    build_builtin_driver_registry,
    execute_generation,
)
from app.features.model_config.public import ExecutionSnapshotCommand, create_execution_snapshot
from app.features.workflow_media.application.live_provider_attempts import (
    finish_live_provider_attempt,
    prepare_live_provider_attempt,
)
from app.features.workflow_media.application.load_context import WorkflowMediaContext
from app.features.workflow_media.application.voice_locks import asset_locks_for_workflow_shot
from app.features.workflow_media.domain.production_strategy import production_strategy_job_extra
from app.features.workflow_media.errors import WorkflowMediaError
from app.features.workflow_media.schemas import WorkflowMediaBatchRequest
from app.models import Shot, VideoJob
from app.services.live_canary_budget import bind_provider_operation_for_reservation
from app.services.provider_prompt_safety import (
    build_provider_video_prompt_fallback,
    provider_text_safety_error_message,
    sanitize_provider_video_prompt,
)
from app.services.video_reference_adapter import (
    build_reference_package_metadata,
    build_video_provider_content,
    enrich_prompt_parameters_with_reference_contract,
)

@dataclass(frozen=True)
class PreparedVideoSubmission:
    video_request: VideoGenerateRequest
    lineage: dict[str, Any]
    consistency_package: dict[str, Any]
    reference_package: Optional[dict[str, Any]]
    final_video_prompt: str
    effective_image_url: Optional[str]
    video_seed: Optional[int]
    audio_route: dict[str, Any]
    dialogue_sync_contract: Optional[dict[str, Any]]
    video_preflight_package: Optional[dict[str, Any]]
    lock_snapshot: dict[str, Any]


@dataclass(frozen=True)
class VideoSubmissionRuntime:
    selected_model: dict[str, Any]
    reference_limits: dict[str, Any]
    selected_model_id: Optional[str]
    selected_provider: Optional[str]
    api_key: Optional[str]
    use_dev_video: bool


@dataclass(frozen=True)
class VideoSubmissionCommand:
    context: WorkflowMediaContext
    request: WorkflowMediaBatchRequest
    shot: Shot
    prepared: PreparedVideoSubmission
    runtime: VideoSubmissionRuntime


@dataclass(frozen=True)
class VideoSubmissionResult:
    video_job: VideoJob
    sync_succeeded_video: bool
    provider_content: dict[str, Any]


def _extra(shot: Shot) -> dict[str, Any]:
    return shot.extra_data if isinstance(shot.extra_data, dict) else {}


def _reference_image_source(prepared: PreparedVideoSubmission) -> Optional[str]:
    reference = prepared.reference_package if isinstance(prepared.reference_package, dict) else {}
    return reference.get("reference_image_source") or prepared.consistency_package.get("reference_image_source")


def _is_persisted_shot_first_frame(command: VideoSubmissionCommand) -> bool:
    shot_url = str(getattr(command.shot, "image_url", None) or "")
    request_url = str(command.prepared.video_request.image_url or "")
    return bool(shot_url and request_url == shot_url)


def _effective_reference_image_source(command: VideoSubmissionCommand) -> Optional[str]:
    if command.request.native_audio and _is_persisted_shot_first_frame(command):
        return "shot_image"
    return _reference_image_source(command.prepared)


def _validate_seedance_first_frame(command: VideoSubmissionCommand, *, image_count: int) -> None:
    model_id = command.runtime.selected_model.get("api_model_id") or command.prepared.video_request.model
    source = _effective_reference_image_source(command)
    if model_id in video_kernel.SEEDANCE_NATIVE_AUDIO_MODEL_IDS and image_count > 0 and source != "shot_image":
        raise WorkflowMediaError(422, {
            "code": "seedance_first_frame_must_be_shot_image",
            "message": "Seedance 1.5 的单图输入会成为视频首帧；复合参考图不能直接用于首帧，请先为该镜头选择场景首帧后重试。",
            "shot_id": command.shot.id,
            "reference_image_source": source,
        })


def _provider_parameter_rejection_detail(error: Exception) -> Optional[dict[str, str]]:
    message = str(error)
    if "InvalidParameter" not in message:
        return None
    if "invalid role specified for image content" in message:
        return {
            "code": "seedance_image_role_rejected",
            "message": "视频模型拒绝了参考图角色参数；本次请求未受理、不会自动重试，请刷新模型适配配置后重试。",
        }
    return {
        "code": "video_provider_parameter_rejected",
        "message": "视频模型拒绝了请求参数；本次请求未受理、不会自动重试，请检查模型适配配置后重试。",
    }


async def _build_submission_data(command: VideoSubmissionCommand) -> dict[str, Any]:
    context, request, prepared = command.context, command.request, command.prepared
    runtime, shot = command.runtime, command.shot
    delivery = await video_kernel.resolve_provider_image_delivery(
        context.db, context.user_id, prepared.effective_image_url,
    )
    provider_image_url = delivery["provider_image_url"]
    prompt = prepared.final_video_prompt
    if delivery["image_url_omitted_reason"]:
        prompt = video_kernel.append_provider_image_note(prompt, delivery["image_url_omitted_reason"])
    protected_texts = []
    if request.native_audio and prepared.dialogue_sync_contract:
        protected_texts.append(str(prepared.dialogue_sync_contract.get("spoken_text") or ""))
    provider_prompt = sanitize_provider_video_prompt(prompt, protected_texts=protected_texts)
    prompt_parameters = video_kernel.video_prompt_parameters(
        prepared.video_request.model_copy(update={"image_url": prepared.effective_image_url}),
        prepared.video_seed, provider_image_url, delivery["image_url_omitted_reason"],
        delivery["image_delivery"],
    )
    prompt_parameters["reference_image_source"] = _reference_image_source(prepared)
    prompt_parameters["provider_reference_image_limit"] = runtime.reference_limits["images"]
    prompt_parameters["generate_audio"] = request.native_audio
    if provider_prompt["sanitized"]:
        prompt_parameters["provider_prompt_sanitized"] = True
        prompt_parameters["provider_prompt_replacements"] = provider_prompt["replacements"]
    return {
        "provider_image_url": provider_image_url, "delivery": delivery,
        "provider_prompt": provider_prompt["prompt"], "prompt_parameters": prompt_parameters,
        "extra_data": _build_extra_data(command, prompt_parameters),
    }


def _build_extra_data(command: VideoSubmissionCommand, prompt_parameters: dict) -> dict:
    context, request, prepared = command.context, command.request, command.prepared
    extra = video_kernel.build_video_extra_data(prepared.video_request, prepared.lineage)
    extra.update(video_kernel.build_video_context_metadata(
        prepared.lineage, prepared.consistency_package["metadata"], prepared.video_seed,
        prepared.consistency_package["context"],
    ))
    extra.update(video_kernel.video_model_metadata(command.runtime.selected_model))
    extra.update(production_strategy_job_extra(
        request.production_strategy, context.effective_video_config_id,
    ))
    extra.update({
        "prompt_parameters": prompt_parameters, "source_prompt": prepared.video_request.prompt,
        "generation_strategy": request.strategy,
        "strategy_routing": context.strategy_video_routing["routing"],
        "strategy_matched_api_model_id": context.strategy_video_routing["matched_api_model_id"],
        "audio_model_config_id": None if request.native_audio else request.audio_model_config_id,
        "audio_route": prepared.audio_route, "video_native_audio": request.native_audio,
    })
    if request.production_strategy == "final_quality":
        extra["visual_consistency_auto_check"] = True
    if prepared.dialogue_sync_contract:
        extra["dialogue_sync_contract"] = prepared.dialogue_sync_contract
    locks = prepared.lock_snapshot
    extra["asset_version_locks"] = locks.get("asset_version_locks") or asset_locks_for_workflow_shot(command.shot)
    extra["asset_lock_snapshot"] = extra["asset_version_locks"]
    if locks.get("voice_lock_snapshot"):
        extra["voice_lock_snapshot"] = locks["voice_lock_snapshot"]
    if prepared.video_preflight_package is not None:
        preflight = prepared.video_preflight_package
        extra["generation_preflight"] = {
            "ready": preflight.get("ready"), "issues": preflight.get("issues") or [],
            "blocking_issue_count": preflight.get("blocking_issue_count") or 0,
        }
    return extra


def _build_provider_content(command: VideoSubmissionCommand, data: dict) -> dict[str, Any]:
    prepared, runtime, request = command.prepared, command.runtime, command.request
    model_id = runtime.selected_model.get("api_model_id") or prepared.video_request.model
    provider_image_url = data["provider_image_url"]
    reference_package = prepared.reference_package
    reference_source = _effective_reference_image_source(command)
    if (
        request.native_audio
        and model_id in video_kernel.SEEDANCE_NATIVE_AUDIO_MODEL_IDS
        and reference_source != "shot_image"
    ):
        raise WorkflowMediaError(422, {
            "code": "native_audio_shot_first_frame_required",
            "message": "原生配音镜头必须先生成当前镜头专用首帧，不能仅靠复合设定板裸生成；请先生成镜头参考图后重试。",
            "shot_id": command.shot.id,
            "shot_number": command.shot.shot_number,
            "reference_image_source": reference_source,
            "repair_action": "generate_shot_first_frame",
        })
    if (
        model_id in video_kernel.SEEDANCE_NATIVE_AUDIO_MODEL_IDS
        and reference_source != "shot_image"
    ):
        package = dict(reference_package or {})
        images = [item for item in package.get("images") or [] if isinstance(item, dict)]
        package["images"] = []
        package["dropped"] = [*(package.get("dropped") or []), *images]
        reference_package = package
        provider_image_url = None
        data["provider_image_url"] = None
        data["prompt_parameters"]["composite_reference_prompt_only"] = True
    content = build_video_provider_content(
        final_prompt=data["provider_prompt"], duration=prepared.video_request.duration,
        resolution=request.resolution, provider_image_url=provider_image_url,
        reference_package=reference_package, model_limits=runtime.reference_limits,
        model_id=runtime.selected_model_id, provider=runtime.selected_provider,
        camera_fixed=False, watermark=video_kernel.PROVIDER_VIDEO_WATERMARK_ENABLED,
    )
    count = int((content.get("metadata") or {}).get("image_count") or 0)
    _validate_seedance_first_frame(command, image_count=count)
    if request.require_provider_reference_image and count <= 0:
        raise WorkflowMediaError(422, {
            "code": "provider_reference_image_missing",
            "message": "真实视频生成需要可提交给云端视频模型的公网参考图；请配置公共静态访问或对象存储后重试",
            "shot_id": command.shot.id, "shot_number": command.shot.shot_number,
            "image_url": prepared.effective_image_url,
            "image_url_omitted_reason": data["delivery"]["image_url_omitted_reason"],
            "model_config_id": command.context.effective_video_config_id,
            "model_id": runtime.selected_model.get("api_model_id") or prepared.video_request.model,
        })
    protocol = runtime.selected_model.get("protocol")
    protocol = protocol if isinstance(protocol, dict) else {}
    data["prompt_parameters"] = enrich_prompt_parameters_with_reference_contract(
        data["prompt_parameters"], content["metadata"], runtime.reference_limits, protocol,
    )
    _record_reference_metadata(command, data, content)
    return content


def _record_reference_metadata(command: VideoSubmissionCommand, data: dict, content: dict) -> None:
    parameters = data["prompt_parameters"]
    data["extra_data"]["prompt_parameters"] = parameters
    data["extra_data"]["reference_package"] = build_reference_package_metadata(
        command.prepared.reference_package, content["metadata"],
    )
    parameters["reference_image_strategy"] = (
        "multimodal_reference_package" if content["mode"] == "multimodal"
        else "single_provider_image"
    )


def _create_kwargs(command: VideoSubmissionCommand, content: dict) -> dict[str, Any]:
    runtime, prepared, request = command.runtime, command.prepared, command.request
    model_id = runtime.selected_model.get("api_model_id") or prepared.video_request.model
    if request.native_audio and model_id not in video_kernel.SEEDANCE_NATIVE_AUDIO_MODEL_IDS:
        raise WorkflowMediaError(422, {
            "code": "native_audio_model_unsupported",
            "message": "原生配音临时开关仅支持 Seedance 1.5 Pro",
            "model_id": model_id,
        })
    return video_kernel.build_ark_video_create_kwargs(
        model=runtime.selected_model.get("model_endpoint_id")
        or runtime.selected_model.get("api_model_id") or prepared.video_request.model,
        content=content["content"], duration=prepared.video_request.duration,
        resolution=request.resolution, camera_fixed=False,
        watermark=video_kernel.PROVIDER_VIDEO_WATERMARK_ENABLED,
        generate_audio=request.native_audio, seed=prepared.video_seed,
    )


def _driver_video_command(
    command: VideoSubmissionCommand, content: dict, prompt: str | None = None,
) -> VideoCommand:
    references = {"image_url": [], "video_url": [], "audio_url": []}
    for item in content.get("content") or []:
        if not isinstance(item, dict) or item.get("type") not in references:
            continue
        value = item.get(item["type"])
        url = value.get("url") if isinstance(value, dict) else None
        if isinstance(url, str) and url:
            references[item["type"]].append(url)
    params = {
        **dict(command.runtime.selected_model["generation_context"].profile.default_params),
        "duration": command.prepared.video_request.duration,
        "resolution": command.request.resolution,
        "camera_fixed": False,
        "watermark": video_kernel.PROVIDER_VIDEO_WATERMARK_ENABLED,
    }
    if command.prepared.video_seed is not None:
        params["seed"] = command.prepared.video_seed
    return VideoCommand(
        prompt=prompt or command.prepared.final_video_prompt,
        reference_images=tuple(references["image_url"]),
        reference_videos=tuple(references["video_url"]),
        reference_audios=tuple(references["audio_url"]),
        native_audio=command.request.native_audio,
        dialogue_contract=command.prepared.dialogue_sync_contract,
        params=params,
    )


async def _reserve(command: VideoSubmissionCommand, job_id: str, retry: bool) -> Optional[str]:
    suffix = "video-retry" if retry else "video"
    return await prepare_live_provider_attempt(
        command.context.db, command.context.series_run, capability="video",
        reservation_id=f"{command.context.workflow.id}:{command.shot.id}:{suffix}:{uuid4()}",
        job_type="video_job", job_id=job_id,
    )


async def _retry_sensitive_prompt(
    command: VideoSubmissionCommand, data: dict, job_id: str, client: Any,
    generation: Any = None, driver_context: Any = None,
) -> tuple[Any, Optional[str], dict]:
    fallback = build_provider_video_prompt_fallback()
    data["provider_prompt"] = fallback["prompt"]
    content = _build_provider_content(command, data)
    reservation = await _reserve(command, job_id, True)
    try:
        if generation is not None and driver_context is not None:
            submission = await execute_generation(
                build_builtin_driver_registry(),
                _driver_video_command(command, content, data["provider_prompt"]),
                driver_context,
            )
            if not submission.provider_task_id:
                raise WorkflowMediaError(422, "视频驱动未返回可轮询的任务标识")
            result = type("SubmittedTask", (), {"id": submission.provider_task_id})()
        else:
            result = video_kernel.submit_ark_video_task(
                create_kwargs={**_create_kwargs(command, content), "content": content["content"]}, client=client,
            )
    except Exception as error:
        cause = getattr(error, "cause", None) or error
        image_error = video_kernel.provider_image_url_error_message(cause, data["provider_image_url"])
        text_error = provider_text_safety_error_message(cause)
        if image_error or text_error:
            await finish_live_provider_attempt(
                command.context.db, command.context.series_run, reservation, submission_failed=True,
            )
        if image_error or text_error:
            raise WorkflowMediaError(422, image_error or text_error) from error
        if cause is not error:
            raise cause
        raise
    parameters = data["prompt_parameters"]
    parameters.update({
        "provider_prompt_safety_retry": True,
        "provider_prompt_safety_retry_reason": "InputTextSensitiveContentDetected",
        "provider_prompt_fallback_replacements": fallback["replacements"],
    })
    _record_reference_metadata(command, data, content)
    return result, reservation, content


def _driver_context_for_submission(
    command: VideoSubmissionCommand, generation: Any, execution_snapshot_id: str | None, client: Any,
) -> Any:
    driver = generation.driver_context
    if client is not None:
        driver = replace(
            driver,
            connection_params={**dict(driver.connection_params), "_ark_client": client},
        )
    return replace(driver, execution_snapshot_id=execution_snapshot_id) if execution_snapshot_id else driver


async def _recover_bound_driver_error(
    command: VideoSubmissionCommand, data: dict, job_id: str, reservation: Optional[str],
    error: DriverError, client: Any, generation: Any, driver: Any,
) -> tuple[str, Optional[str], dict]:
    cause = getattr(error, "cause", None) or error
    image_error = video_kernel.provider_image_url_error_message(cause, data.get("provider_image_url"))
    text_error = provider_text_safety_error_message(cause)
    parameter_error = _provider_parameter_rejection_detail(cause)
    if image_error or text_error or parameter_error:
        await finish_live_provider_attempt(
            command.context.db, command.context.series_run, reservation, submission_failed=True,
        )
    if text_error and client is not None and os.getenv("LIVE_CANARY_PROVIDER_RETRIES", "1") != "0":
        result, retry_reservation, retry_content = await _retry_sensitive_prompt(
            command, data, job_id, client, generation, driver,
        )
        task_id = result.id
        if retry_reservation:
            await bind_provider_operation_for_reservation(
                command.context.db, command.context.series_run,
                reservation_id=retry_reservation, provider_task_id=task_id,
            )
        return task_id, retry_reservation, retry_content
    if image_error or text_error or parameter_error:
        raise WorkflowMediaError(422, image_error or text_error or parameter_error) from error
    if getattr(error, "cause", None) is not None:
        raise error.cause
    raise WorkflowMediaError(422, str(error)) from error


async def _submit_bound_driver(
    command: VideoSubmissionCommand, data: dict, content: dict, job_id: str,
    execution_snapshot_id: str | None, generation: Any,
) -> tuple[str, Optional[str], dict]:
    reservation = await _reserve(command, job_id, False)
    client = None
    if generation.driver_context.driver_key == "volcano_ark_video_v3":
        client = video_kernel.create_ark_client(
            getattr(command.runtime, "api_key", None), command.runtime.selected_model.get("base_url"),
        )
    driver = _driver_context_for_submission(command, generation, execution_snapshot_id, client)
    try:
        submission = await execute_generation(
            build_builtin_driver_registry(),
            _driver_video_command(command, content, data.get("provider_prompt")), driver,
        )
    except DriverError as error:
        return await _recover_bound_driver_error(
            command, data, job_id, reservation, error, client, generation, driver,
        )
    task_id = submission.provider_task_id
    if not task_id:
        raise WorkflowMediaError(422, "视频驱动未返回可轮询的任务标识")
    if reservation:
        await bind_provider_operation_for_reservation(
            command.context.db, command.context.series_run,
            reservation_id=reservation, provider_task_id=task_id,
        )
    return task_id, reservation, content


async def _submit_live(
    command: VideoSubmissionCommand, data: dict, content: dict, job_id: str,
    execution_snapshot_id: str | None = None,
) -> tuple[str, Optional[str], dict]:
    generation = command.runtime.selected_model.get("generation_context")
    if generation is not None:
        return await _submit_bound_driver(
            command, data, content, job_id, execution_snapshot_id, generation,
        )
    client = video_kernel.create_ark_client(
        command.runtime.api_key, command.runtime.selected_model.get("base_url"),
    )
    reservation = await _reserve(command, job_id, False)
    try:
        result = video_kernel.submit_ark_video_task(
            create_kwargs=_create_kwargs(command, content), client=client,
        )
    except Exception as error:
        image_error = video_kernel.provider_image_url_error_message(error, data["provider_image_url"])
        text_error = provider_text_safety_error_message(error)
        parameter_error = _provider_parameter_rejection_detail(error)
        if image_error or text_error or parameter_error:
            await finish_live_provider_attempt(
                command.context.db, command.context.series_run, reservation, submission_failed=True,
            )
        if image_error:
            raise WorkflowMediaError(422, image_error) from error
        if parameter_error:
            raise WorkflowMediaError(422, parameter_error) from error
        if not text_error:
            raise
        if os.getenv("LIVE_CANARY_PROVIDER_RETRIES", "1") == "0":
            raise WorkflowMediaError(422, text_error) from error
        result, reservation, content = await _retry_sensitive_prompt(
            command, data, job_id, client,
        )
    task_id = result.id
    if reservation:
        await bind_provider_operation_for_reservation(
            command.context.db, command.context.series_run,
            reservation_id=reservation, provider_task_id=task_id,
        )
    return task_id, reservation, content


async def _create_execution_snapshot(
    command: VideoSubmissionCommand, content: dict, job_id: str,
) -> str | None:
    generation = command.runtime.selected_model.get("generation_context")
    if generation is None:
        return None
    metadata = content.get("metadata") if isinstance(content, dict) else {}
    snapshot = await create_execution_snapshot(
        command.context.db,
        ExecutionSnapshotCommand(
            user_id=command.context.user_id,
            run_id=getattr(command.context.series_run, "id", None),
            job_id=job_id,
            task=generation.binding.task,
            capability=generation.binding.capability,
            binding=generation.binding,
            recipe_version_id=getattr(generation, "recipe_version_id", None),
            prompt_profile_version_id=getattr(generation, "prompt_profile_version_id", None),
            sanitized_params={
                "duration": command.prepared.video_request.duration,
                "resolution": command.request.resolution,
                "native_audio": command.request.native_audio,
                "reference_image_count": int((metadata or {}).get("image_count") or 0),
                "reference_video_count": int((metadata or {}).get("video_count") or 0),
                "reference_audio_count": int((metadata or {}).get("audio_count") or 0),
                "seed": command.prepared.video_seed,
            },
        ),
    )
    return snapshot.id


def _build_job(
    command: VideoSubmissionCommand, data: dict, job_id: str,
    task_id: Optional[str], reservation: Optional[str], execution_snapshot_id: str | None,
) -> VideoJob:
    context, runtime, prepared, shot = command.context, command.runtime, command.prepared, command.shot
    video_url = dev_video_url(job_id, duration_seconds=prepared.video_request.duration) if runtime.use_dev_video else None
    job = VideoJob(
        id=job_id, user_id=context.user_id, project_id=_extra(shot).get("project_id"),
        workflow_id=context.workflow.id, shot_id=shot.id, task_id=task_id, title=f"镜头{shot.shot_number} 视频",
        prompt=data["provider_prompt"],
        model_id=runtime.selected_model.get("api_model_id") or prepared.video_request.model,
        model_name=(f"{runtime.selected_model.get('model_name')} (DEV_MODE)"
                    if runtime.use_dev_video else runtime.selected_model.get("model_name")),
        duration=prepared.video_request.duration, resolution=command.request.resolution,
        image_url=data.get("provider_image_url"),
        status="succeeded" if runtime.use_dev_video else "pending",
        progress=100 if runtime.use_dev_video else 10, video_url=video_url,
        cover_url=None, extra_data=data["extra_data"],
    )
    if reservation:
        run = context.series_run
        accounting = run.cost_summary["reservations"][reservation]
        job.extra_data = {**job.extra_data, "live_canary_accounting": {
            "series_run_id": run.id, "reservation_id": reservation,
            "provider_task_id": task_id, "capability": "video",
            "operation_id": accounting.get("operation_id"),
        }}
    if execution_snapshot_id:
        job.extra_data = {**job.extra_data, "execution_snapshot_id": execution_snapshot_id}
    return job


async def submit_video(command: VideoSubmissionCommand) -> VideoSubmissionResult:
    """Prepare provider content, submit when live, and construct an unpersisted VideoJob."""
    if command.request.strategy != "separate_video_tts":
        raise WorkflowMediaError(422, "视频提交适配器仅支持 separate_video_tts 策略")
    data = await _build_submission_data(command)
    content = _build_provider_content(command, data)
    job_id, reservation = str(uuid4()), None
    execution_snapshot_id = await _create_execution_snapshot(command, content, job_id)
    task_id = f"dev-video-{job_id}" if command.runtime.use_dev_video else None
    if not command.runtime.use_dev_video:
        task_id, reservation, content = await _submit_live(
            command, data, content, job_id, execution_snapshot_id,
        )
    job = _build_job(command, data, job_id, task_id, reservation, execution_snapshot_id)
    return VideoSubmissionResult(job, command.runtime.use_dev_video, content)
