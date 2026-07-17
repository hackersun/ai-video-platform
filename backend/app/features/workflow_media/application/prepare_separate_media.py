"""Prepare transport-neutral inputs for separate video and TTS generation."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlalchemy import desc, select

from app.core.api_key_utils import get_user_api_key
from app.core.dev_generation import is_dev_mode
from app.core.model_registry import get_model_reference_limits, get_task_default
from app.features.video_generation import public as video_kernel
from app.features.workflow_media.application.load_context import WorkflowMediaContext
from app.features.workflow_media.application.reference_packages import (
    build_final_quality_reference_packages,
    supports_reference_package,
)
from app.features.workflow_media.application.voice_locks import (
    FinalQualityLockCommand,
    build_final_quality_lock_snapshots,
    clean_character_label,
    primary_tts_character_name,
    provider_compatible_tts_voice,
    shot_subtitle_text,
)
from app.features.workflow_media.errors import WorkflowMediaError
from app.features.workflow_media.schemas import WorkflowMediaBatchRequest
from app.models import Shot
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.services.audio_route_service import resolve_shot_audio_route
from app.services.consistency_preflight import (
    build_generation_context_package,
    preflight_failure_detail,
)
from app.services.dialogue_parser import parse_dialogue
from app.services.reference_package_builder import bind_reference_package, build_reference_package
from app.services.video_reference_adapter import apply_seedance_contract_limits
from app.services.volcano_speech_tts import configure_volcano_speech_endpoint


@dataclass(frozen=True)
class PrepareSeparateMediaCommand:
    context: WorkflowMediaContext
    request: WorkflowMediaBatchRequest


@dataclass(frozen=True)
class PreparedSeparateMedia:
    selected_video_model: Dict[str, Any]
    selected_video_model_id: Optional[str]
    selected_video_provider: Optional[str]
    video_reference_limits: Dict[str, Any]
    selected_audio_model: Optional[Dict[str, Any]]
    final_quality_snapshots: Dict[str, Dict[str, Any]]
    video_api_key: Optional[str]
    audio_api_key: Optional[str]
    use_dev_video: bool
    use_dev_audio: bool
    prepared_shots: Dict[str, Dict[str, Any]]


def _is_tts_model(model: LLMModel) -> bool:
    model_type = (model.model_type or "").lower()
    capabilities = [str(item).lower() for item in (model.capabilities or [])]
    return model_type in {"tts", "audio", "speech"} or any(
        item in {"text-to-speech", "speech", "tts"} or "speech" in item or "tts" in item
        for item in capabilities
    )


def _audio_model(config: LLMConfig, model: LLMModel, provider: LLMProvider) -> Dict[str, Any]:
    extra = config.extra_params if isinstance(config.extra_params, dict) else {}
    provider_id = provider.name or provider.id
    base_url = extra.get("base_url") or model.base_url or provider.base_url
    if provider_id == "volcano":
        base_url = configure_volcano_speech_endpoint(base_url, extra)
    return {
        "config_id": config.id,
        "provider_id": provider_id,
        "model_id": model.model_id,
        "model_name": model.model_name_cn or model.model_name,
        "capabilities": model.capabilities or [],
        "test_status": config.test_status,
        "base_url": base_url,
        "api_key": config.get_api_key_decrypted(),
    }


async def _resolve_saved_tts_model(
    context: WorkflowMediaContext, config_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not config_id:
        return None
    result = await context.db.execute(
        select(LLMConfig, LLMModel, LLMProvider)
        .join(LLMModel, LLMConfig.model_id == LLMModel.id)
        .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
        .where(
            LLMConfig.id == config_id,
            LLMConfig.user_id == context.user_id,
            LLMConfig.is_active == True,
            LLMModel.is_active == True,
            LLMProvider.is_active == True,
        ).limit(1)
    )
    row = result.first()
    if not row:
        raise WorkflowMediaError(404, "所选声音模型配置不存在或已停用")
    config, model, provider = row
    if not _is_tts_model(model):
        raise WorkflowMediaError(422, "所选模型配置不支持声音/TTS能力")
    return _audio_model(config, model, provider)


async def _resolve_default_tts_model(context: WorkflowMediaContext) -> Optional[Dict[str, Any]]:
    supported = {"minimax", "volcano"}
    result = await context.db.execute(
        select(LLMConfig, LLMModel, LLMProvider)
        .join(LLMModel, LLMConfig.model_id == LLMModel.id)
        .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
        .where(
            LLMConfig.user_id == context.user_id,
            LLMConfig.is_active == True,
            LLMModel.is_active == True,
            LLMProvider.is_active == True,
        ).order_by(desc(LLMConfig.is_default), desc(LLMConfig.updated_at), desc(LLMConfig.created_at))
    )
    for config, model, provider in result.all():
        candidate = _audio_model(config, model, provider)
        if candidate["provider_id"] in supported and _is_tts_model(model) and candidate["api_key"]:
            return candidate
    default = (get_task_default("tts_dialogue") or {}).get("default_model") or {}
    if not default:
        return None
    provider_id = default.get("provider_id", "local")
    api_key, base_url = (None, None)
    if provider_id in supported:
        api_key, base_url = await get_user_api_key(
            context.db, context.user_id, provider_id, raise_if_missing=False,
        )
    return {
        "config_id": None, "provider_id": provider_id,
        "model_id": default.get("api_model_id") or default.get("id") or "local.dev_tts",
        "model_name": default.get("display_name", "DEV_MODE 语音合成"),
        "capabilities": default.get("capabilities") or ["text-to-speech"],
        "test_status": "configured" if api_key else None, "base_url": base_url, "api_key": api_key,
    }


def _tts_unconfigured_detail(command: PrepareSeparateMediaCommand, model: Optional[dict]) -> dict:
    request, workflow = command.request, command.context.workflow
    return {
        "code": "real_tts_model_unconfigured",
        "message": f"真实 TTS 需要配置并验证声音模型 {model.get('model_name') if model else '默认 TTS'}，不能复用未验证的视频/文本模型 Key。请先在模型配置中保存可用的 MiniMax 或火山 TTS 配置，再从前端重新生成。",
        "model_config_id": request.audio_model_config_id,
        "model_id": model.get("model_id") if model else None,
        "provider_id": model.get("provider_id") if model else None,
        "workflow_id": workflow.id,
    }


def _shot_prompt(shot: Shot) -> str:
    subtitle = shot_subtitle_text(shot)
    parts = [
        shot.prompt, shot.visual_description, f"对白/字幕：{subtitle}" if subtitle else None,
        f"镜头角度：{shot.camera_angle}" if shot.camera_angle else None,
        f"运镜：{shot.camera_movement}" if shot.camera_movement else None,
        f"光影：{shot.lighting}" if shot.lighting else None,
        f"色彩：{shot.color_grading}" if shot.color_grading else None,
    ]
    return "；".join(str(item).strip() for item in parts if item) or f"镜头{shot.shot_number}"


def _dialogue_contract(
    shot: Shot, subtitle: str, duration: float, *, video_native_audio: bool = False,
) -> Optional[dict]:
    if not subtitle:
        return None
    fallback = primary_tts_character_name(shot, subtitle)
    segments = []
    for item in parse_dialogue(subtitle):
        text = str(item.get("text") or "").strip()
        if text:
            segments.append({"speaker": clean_character_label(item.get("character")) or fallback, "text": text})
    if not segments:
        segments.append({"speaker": fallback, "text": subtitle.strip()})
    speakers = [item["speaker"] for item in segments if item.get("speaker")]
    end = round(float(duration), 3)
    return {
        "version": 1, "speaker": speakers[0] if speakers else fallback, "subtitle_text": subtitle,
        "spoken_text": "\n".join(item["text"] for item in segments if item.get("text")) or subtitle,
        "segments": [{**item, "start_seconds": 0.0, "end_seconds": end} for item in segments],
        "start_seconds": 0.0, "end_seconds": end,
        "audio_source": "video_native_audio" if video_native_audio else "separate_tts",
        "video_native_audio": video_native_audio, "mouth_performance": "match_spoken_text_only",
        "requires_segmented_tts": len(set(speakers)) > 1,
    }


def _append_dialogue_prompt(prompt: str, contract: Optional[dict]) -> str:
    if not contract or not contract.get("spoken_text"):
        return prompt
    speaker = contract.get("speaker") or "当前说话角色"
    timing = f"{contract.get('end_seconds')} 秒内" if contract.get("end_seconds") else "本镜头内"
    if contract.get("video_native_audio"):
        segments = contract.get("segments") or []
        dialogue = "\n".join(
            f"{item.get('speaker') or speaker}：{str(item.get('text') or '').strip()}"
            for item in segments if str(item.get("text") or "").strip()
        )
        speakers = list(dict.fromkeys(
            str(item.get("speaker") or speaker) for item in segments
            if str(item.get("speaker") or speaker).strip()
        ))
        speaker_rule = (
            f"说话人仅限：{'、'.join(speakers)}；各角色必须按以下归属逐句说话，不得串词：\n{dialogue}；"
            if len(speakers) > 1 else
            f"唯一说话人：{speaker}；必须完整、清晰地说：『{str(contract['spoken_text']).strip()}』；"
        )
        return (
            f"{prompt}\n\n原生有声视频约束（硬性）：本镜头由视频模型直接生成画面、普通话人声和环境声；"
            f"{speaker_rule}"
            "不得增删或改写台词，不得加入旁白或其他角色人声；人物必须自然开口，口型逐句匹配台词，"
            f"在{timing}完成开口、停顿和收口；动作、表情与语气一致，环境声不得遮盖对白。"
        )
    return (
        f"{prompt}\n\n对白同步约束（硬性）：本镜头采用视频与TTS分步生产，"
        "视频模型只做无声口型和表演，不要生成原生对白或人声，不要改写台词；"
        f"说话人：{speaker}；口型表演对应台词：『{str(contract['spoken_text']).strip()}』；"
        f"画面动作需要在{timing}为这句台词预留自然开口、停顿和收口节奏。"
    )


def _validate_dialogue(shot: Shot, subtitle: str, contract: Optional[dict]) -> None:
    if not contract or contract.get("video_native_audio") or not contract.get("requires_segmented_tts"):
        return
    speakers = [item.get("speaker") for item in contract.get("segments", []) if item.get("speaker")]
    raise WorkflowMediaError(422, {
        "code": "multi_speaker_dialogue_requires_segmented_tts",
        "message": "同一镜头包含多个说话人，当前分步生产不能用单个 TTS 任务保证多角色声线一致；请拆分镜头或启用分段 TTS 后再生成。",
        "shot_id": shot.id, "shot_number": shot.shot_number,
        "speakers": list(dict.fromkeys(speakers)), "subtitle_text": subtitle,
    })


async def _model_inputs(command: PrepareSeparateMediaCommand) -> dict:
    context, request = command.context, command.request
    try:
        video = await video_kernel.resolve_video_model_config(
            context.db, context.user_id, None, context.effective_video_config_id,
        )
    except video_kernel.VideoGenerationError as error:
        raise WorkflowMediaError(error.status_code, error.detail) from error
    model_id = video.get("api_model") or video.get("api_model_id") or video.get("model_id") or video.get("config_model_id")
    provider = video.get("provider") or video.get("provider_id") or video.get("provider_name")
    limits = apply_seedance_contract_limits(
        get_model_reference_limits(video.get("api_model_id") or video.get("config_model_id") or ""),
        model_id=model_id, provider=provider,
    )
    audio = None if request.native_audio else await _resolve_saved_tts_model(context, request.audio_model_config_id)
    if not audio and request.audio_mode != "none" and not request.native_audio:
        audio = await _resolve_default_tts_model(context)
    return {"video": video, "model_id": model_id, "provider": provider, "limits": limits, "audio": audio}


async def _quality_inputs(command: PrepareSeparateMediaCommand, values: dict) -> tuple[dict, dict]:
    context, request = command.context, command.request
    if request.production_strategy != "final_quality":
        return {}, {}
    references = await build_final_quality_reference_packages(
        context.db, context.user_id, context.workflow, context.shots,
        model_limits=values["limits"], resolve_public_url=video_kernel.resolve_provider_image_delivery,
        provider_id=str(values["provider"] or "volcano"),
        model_id=str(values["model_id"] or values["video"].get("config_model_id") or ""),
    )
    locks = await build_final_quality_lock_snapshots(FinalQualityLockCommand(
        context.db, context.user_id, context.workflow, context.shots,
        requested_story_bible_id=request.story_bible_id,
        default_voice=provider_compatible_tts_voice(request.voice_model, values["audio"]),
        default_speed=request.speed, default_voice_source="provider_default_tts",
    ))
    return references, locks


def _runtime_flags(command: PrepareSeparateMediaCommand, values: dict) -> tuple[Optional[str], Optional[str], bool, bool]:
    request = command.request
    video_key = values["video"].get("api_key")
    audio_key = values["audio"].get("api_key") if values["audio"] else None
    dev_video = not video_key and is_dev_mode() and not request.require_real_video
    dev_audio = request.native_audio or request.audio_mode == "none" or bool(audio_key) or is_dev_mode()
    if request.require_real_video and not video_key:
        model = values["video"]
        raise WorkflowMediaError(422, {
            "code": "real_video_model_unconfigured",
            "message": f"真实视频生成需要为所选视频模型 {model.get('model_name') or model.get('model_id')} 配置并验证 API Key，不能回退到 DEV_MODE 占位视频",
            "model_config_id": command.context.effective_video_config_id,
            "model_id": model.get("api_model_id") or model.get("model_id"),
        })
    if not video_key and not dev_video:
        model = values["video"]
        raise WorkflowMediaError(422, f"所选视频模型 {model.get('model_name') or model.get('model_id')} 未配置可用 API Key，请在模型配置中验证后再生成")
    return video_key, audio_key, dev_video, dev_audio


async def _reference_for_shot(command: PrepareSeparateMediaCommand, values: dict, shot: Shot, lineage: dict) -> Optional[dict]:
    if not supports_reference_package(values["limits"]) and not command.request.require_provider_reference_image:
        return None
    package = values["quality_references"].get(shot.id)
    if package is None:
        package = await build_reference_package(
            command.context.db, command.context.user_id, shot=shot, lineage=lineage,
            model_limits=values["limits"], resolve_public_url=video_kernel.resolve_provider_image_delivery,
        )
        package = await bind_reference_package(
            command.context.db, package, provider_id=str(values["provider"] or "volcano"),
            model_id=str(values["model_id"] or values["video_request"].model),
            allow_canonical_public_fallback=True,
        )
    return package


async def _preflights(command: PrepareSeparateMediaCommand, values: dict) -> tuple[Optional[dict], Optional[dict]]:
    if is_dev_mode():
        return None, None
    context, request, shot = command.context, command.request, values["shot"]
    common = {
        "novel_id": context.workflow.novel_id, "chapter_id": context.workflow.chapter_id,
        "script_id": context.workflow.script_id,
        "storyboard_id": context.workflow.storyboard_id or shot.storyboard_id, "shot_id": shot.id,
    }
    video = await build_generation_context_package(
        context.db, context.user_id, task_type="shot_video",
        model_config_id=context.effective_video_config_id, image_url=values["effective_image_url"],
        production_mode=True, require_public_reference_image=bool(values["effective_image_url"]), **common,
    )
    if not video.get("ready"):
        raise WorkflowMediaError(422, preflight_failure_detail(video))
    tts = None
    if values["needs_tts"]:
        tts = await build_generation_context_package(
            context.db, context.user_id, task_type="tts_dialogue",
            model_config_id=request.audio_model_config_id, production_mode=True, **common,
        )
        if not tts.get("ready"):
            raise WorkflowMediaError(422, preflight_failure_detail(tts))
    return video, tts


async def _prepare_shot(command: PrepareSeparateMediaCommand, shared: dict, shot: Shot) -> dict:
    context, request = command.context, command.request
    duration = float(request.duration_seconds or shot.duration or 4)
    video_request = video_kernel.VideoGenerateRequest(
        prompt=_shot_prompt(shot),
        model=shared["video"].get("config_model_id") or shared["video"].get("api_model_id") or video_kernel.VIDEO_MODEL_ID,
        model_config_id=context.effective_video_config_id, duration=max(4, min(10, int(round(duration)))),
        resolution=request.resolution, workflow_id=context.workflow.id, novel_id=context.workflow.novel_id,
        chapter_id=context.workflow.chapter_id, script_id=context.workflow.script_id,
        storyboard_id=context.workflow.storyboard_id or shot.storyboard_id, shot_id=shot.id,
        image_url=shot.image_url, use_consistency_context=True,
    )
    try:
        lineage = await video_kernel.resolve_video_lineage(context.db, context.user_id, video_request)
        package = await video_kernel.build_video_consistency_package(
            video_kernel.VideoConsistencyPackageContext(context.db, context.user_id, video_request, lineage)
        )
    except (video_kernel.VideoGenerationError, video_kernel.VideoConsistencyPackageError) as error:
        raise WorkflowMediaError(error.status_code, error.detail) from error
    local = {**shared, "video_request": video_request}
    reference = await _reference_for_shot(command, local, shot, lineage)
    image_url = (reference or {}).get("reference_image") or package["reference_image"]
    subtitle = shot_subtitle_text(shot)
    audio_route = (
        {"route": "video_native_audio", "reason": "temporary_seedance_native_audio"}
        if request.native_audio else
        {"route": "silent", "reason": "audio_mode_none"}
        if request.audio_mode == "none" else
        resolve_shot_audio_route(shot, model_limits=shared["limits"], voice_lock=None)
    )
    contract = _dialogue_contract(
        shot, subtitle, duration, video_native_audio=request.native_audio,
    ) if request.audio_mode != "none" and audio_route.get("route") in {"tts", "video_native_audio"} and subtitle else None
    _validate_dialogue(shot, subtitle, contract)
    needs_tts = bool(not request.native_audio and request.audio_mode != "none" and audio_route.get("route") == "tts" and subtitle)
    if needs_tts and not shared["audio_key"] and not shared["dev_audio"]:
        raise WorkflowMediaError(422, _tts_unconfigured_detail(command, shared["audio"]))
    video_preflight, tts_preflight = await _preflights(command, {"shot": shot, "effective_image_url": image_url, "needs_tts": needs_tts})
    return {
        "duration": duration, "video_request": video_request, "lineage": lineage, "package": package,
        "reference_package": reference, "final_video_prompt": _append_dialogue_prompt(package["final_prompt"], contract),
        "effective_image_url": image_url,
        "video_seed": video_kernel.resolve_video_seed(video_request, lineage, package["metadata"]),
        "subtitle_text": subtitle, "dialogue_sync_contract": contract, "audio_route": audio_route,
        "video_preflight_package": video_preflight, "tts_preflight_package": tts_preflight,
    }


async def prepare_separate_media(command: PrepareSeparateMediaCommand) -> PreparedSeparateMedia:
    values = await _model_inputs(command)
    references, locks = await _quality_inputs(command, values)
    video_key, audio_key, dev_video, dev_audio = _runtime_flags(command, values)
    shared = {
        **values, "quality_references": references, "audio_key": audio_key, "dev_audio": dev_audio,
    }
    prepared = {}
    for shot in command.context.shots:
        prepared[shot.id] = await _prepare_shot(command, shared, shot)
    return PreparedSeparateMedia(
        values["video"], values["model_id"], values["provider"], values["limits"], values["audio"],
        locks, video_key, audio_key, dev_video, dev_audio, prepared,
    )
