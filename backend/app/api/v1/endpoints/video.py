"""
视频生成 API 端点
支持火山引擎豆包视频模型

使用官方SDK: volcengine-python-sdk[ark]
模型: doubao-seedance-1-5-pro-251215 (Doubao-Seedance-1.5-pro)

完整异步流程:
1. POST /video/generate -> 提交任务，返回 task_id
2. GET /video/status/{task_id} -> 查询任务状态
3. GET /video/jobs -> 获取历史任务
"""

from app.core.time_utils import utc_now
from typing import Any, List, Optional
from datetime import datetime
from uuid import uuid4
import hashlib
import ipaddress
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, select, desc
from pydantic import BaseModel, Field

from app.core.api_key_utils import get_user_api_key
from app.core.database import get_db
from app.core.dev_generation import dev_video_url, is_dev_mode
from app.core.model_registry import find_model, get_model_reference_limits, get_provider, get_task_default, get_video_model_catalog
from app.core.security import get_current_user_id
from app.core.volcano_agent_plan_config import VOLCANO_AGENT_PLAN_PROVIDER_ID, find_volcano_agent_plan_model
from app.models.video_job import VideoJob
from app.services.media_persistence import persist_remote_media_url
from app.services.media_delivery import resolve_provider_media_url
from app.services.consistency_context import get_project_for_context, get_story_bible_for_context
from app.services.consistency_preflight import build_generation_context_package
from app.services.novel_continuity import build_novel_continuity_package
from app.services.provider_prompt_safety import (
    build_provider_video_prompt_fallback,
    provider_text_safety_error_message,
    sanitize_provider_video_prompt,
)
from app.services.prompt_composer import compose_generation_prompt
from app.services.prompt_skill_service import active_prompt_skill_entries
from app.services.reference_package_builder import bind_reference_package, build_reference_package
from app.services.video_reference_adapter import (
    apply_seedance_contract_limits,
    build_reference_package_metadata,
    build_video_provider_content,
    enrich_prompt_parameters_with_reference_contract,
)
from app.services.asset_lock_service import AssetLockService
from app.services.live_canary_budget import settle_provider_operation
from app.services.story_prompt_context import build_video_continuity_constraints, load_story_prompt_context
from app.api.v1.endpoints.dashboard import log_activity
from app.features.video_generation.public import (
    MAX_PROVIDER_SEED, PROVIDER_VIDEO_WATERMARK_ENABLED,
    VIDEO_MODEL_ID,
    VideoConsistencyPackageContext,
    VideoConsistencyPackageError,
    VideoGenerateRequest,
    VideoGenerationError,
    VideoJobSyncCommand,
    append_provider_image_note,
    build_video_context_metadata,
    build_ark_video_create_kwargs,
    build_video_extra_data,
    build_video_consistency_package,
    collect_character_multiview_refs,
    create_ark_client,
    derive_stable_seed,
    extract_shot_generation_context,
    get_video_model_name,
    json_dict,
    provider_image_url_error_message,
    resolve_provider_image_delivery,
    resolve_video_job_client_config,
    resolve_video_lineage,
    resolve_video_model_config,
    resolve_video_seed,
    sync_video_job_and_shot,
    has_video_generation_driver, submit_bound_video_task,
    video_model_metadata,
    video_prompt_parameters,
)

router = APIRouter(tags=["视频生成"])


# ============== 常量配置 ==============

ARK_VIDEO_PROVIDER_IDS = {"volcano", VOLCANO_AGENT_PLAN_PROVIDER_ID}

# 兼容旧引用；前端模型选择以 /video/models 返回的统一 registry 目录为准。
VIDEO_MODEL_OPTIONS = [
    {"id": "volcano.seedance.2_0", "label": "豆包 Seedance 2.0", "desc": "默认推荐，多模态参考生成"},
    {"id": "alibaba.happyhorse.1_1", "label": "HappyHorse-1.1", "desc": "高质量备选，动态与一致性优先"},
    {"id": "kling.3_0_omni", "label": "可灵 3.0 Omni", "desc": "高质量备选，多镜头与音画能力"},
    {"id": "pixverse.c1", "label": "PixVerse C1", "desc": "动漫/动作专项"},
    {"id": "volcano.seedance.1_5_pro", "label": "豆包 Seedance 1.5 Pro", "desc": "低价/兼容"},
    {"id": "kling.v2_6", "label": "可灵 V2.6", "desc": "低价/兼容"},
    {"id": "kling.o1", "label": "可灵 O1", "desc": "低价/兼容"},
]

STATIC_ROOT = Path(__file__).resolve().parents[4] / "static"
# ============== 请求/响应模型 ==============



class VideoGenerateResponse(BaseModel):
    """视频生成响应"""
    task_id: str
    job_id: str  # 新增：数据库job ID
    status: str
    message: str
    project_id: Optional[str] = None
    workflow_id: Optional[str] = None
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    storyboard_id: Optional[str] = None
    shot_id: Optional[str] = None


class VideoStatusResponse(BaseModel):
    """视频状态响应"""
    task_id: str
    job_id: Optional[str] = None
    status: str  # pending, running, succeeded, failed
    video_url: Optional[str] = None
    cover_url: Optional[str] = None
    message: str
    progress: Optional[int] = Field(None, description="进度百分比")
    duration: Optional[int] = None
    resolution: Optional[str] = None


class VideoJobResponse(BaseModel):
    """视频任务响应"""
    id: str
    task_id: Optional[str] = None
    title: Optional[str] = None
    prompt: Optional[str] = None
    project_id: Optional[str] = None
    workflow_id: Optional[str] = None
    shot_id: Optional[str] = None
    shot_number: Optional[int] = None
    storyboard_id: Optional[str] = None
    storyboard_title: Optional[str] = None
    script_id: Optional[str] = None
    script_title: Optional[str] = None
    chapter_id: Optional[str] = None
    chapter_title: Optional[str] = None
    chapter_number: Optional[int] = None
    novel_id: Optional[str] = None
    novel_title: Optional[str] = None
    provider_id: Optional[str] = None
    model_config_id: Optional[str] = None
    config_model_id: Optional[str] = None
    api_model_id: Optional[str] = None
    model_endpoint_id: Optional[str] = None
    model_test_status: Optional[str] = None
    image_url: Optional[str] = None
    extra_data: dict = Field(default_factory=dict)
    prompt_parameters: dict = Field(default_factory=dict)
    model_name: Optional[str] = None
    status: str
    progress: int
    video_url: Optional[str] = None
    cover_url: Optional[str] = None
    error_message: Optional[str] = None
    duration: Optional[int] = None
    resolution: Optional[str] = None
    subtitle_text: Optional[str] = None
    character_refs: List[dict] = Field(default_factory=list)
    scene_refs: List[dict] = Field(default_factory=list)
    prop_refs: List[dict] = Field(default_factory=list)
    event_refs: List[dict] = Field(default_factory=list)
    environment_context: Optional[str] = None
    character_multiview_refs: List[dict] = Field(default_factory=list)
    consistency: dict = Field(default_factory=dict)
    seed: Optional[int] = None
    source_prompt: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class VideoJobUpdateRequest(BaseModel):
    status: Optional[str] = Field(None, description="任务状态")
    progress: Optional[int] = Field(None, ge=0, le=100, description="任务进度")
    title: Optional[str] = Field(None, max_length=200, description="任务标题")
    error_message: Optional[str] = Field(None, description="错误信息")














def _provider_safe_image_url(image_url: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Return a cloud-provider-safe image URL and the omission reason if unusable."""
    if not image_url:
        return None, None

    candidate = image_url.strip()
    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None, "参考图不是公网 http(s) URL，云端视频模型无法直接访问"

    hostname = parsed.hostname
    if not hostname:
        return None, "参考图 URL 缺少有效域名，云端视频模型无法访问"

    host = hostname.lower()
    if host in {"localhost", "local"} or host.endswith(".local"):
        return None, "参考图地址指向本机或局域网域名，云端视频模型无法访问"

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return candidate, None

    if not ip.is_global:
        return None, "参考图地址指向内网、本机或保留 IP，云端视频模型无法访问"
    return candidate, None












def _extract_video_result(get_result):
    """Extract output fields from the different ARK response shapes in use."""
    video_url = None
    cover_url = None
    for attr in ("content", "output"):
        payload = getattr(get_result, attr, None)
        if payload:
            video_url = video_url or getattr(payload, "video_url", None)
            cover_url = cover_url or getattr(payload, "last_frame_url", None)
    return video_url, cover_url














def _build_video_job_response(job: VideoJob) -> VideoJobResponse:
    extra = json_dict(job.extra_data)
    consistency = json_dict(extra.get("consistency"))
    seed = extra.get("seed") if extra.get("seed") is not None else consistency.get("seed")
    return VideoJobResponse(
        id=job.id,
        task_id=job.task_id,
        title=job.title,
        prompt=job.prompt,
        project_id=job.project_id or extra.get("project_id"),
        workflow_id=job.workflow_id or extra.get("workflow_id"),
        shot_id=extra.get("shot_id"),
        shot_number=extra.get("shot_number"),
        storyboard_id=extra.get("storyboard_id"),
        storyboard_title=extra.get("storyboard_title"),
        script_id=extra.get("script_id"),
        script_title=extra.get("script_title"),
        chapter_id=extra.get("chapter_id"),
        chapter_title=extra.get("chapter_title"),
        chapter_number=extra.get("chapter_number"),
        novel_id=extra.get("novel_id"),
        novel_title=extra.get("novel_title"),
        provider_id=extra.get("provider_id"),
        model_config_id=extra.get("model_config_id"),
        config_model_id=extra.get("config_model_id"),
        api_model_id=extra.get("api_model_id"),
        model_endpoint_id=extra.get("model_endpoint_id"),
        model_test_status=extra.get("model_test_status"),
        image_url=job.image_url,
        extra_data=extra,
        prompt_parameters=extra.get("prompt_parameters") or {},
        model_name=job.model_name,
        status=job.status,
        progress=job.progress,
        video_url=job.video_url,
        cover_url=job.cover_url,
        error_message=job.error_message,
        duration=job.duration,
        resolution=job.resolution,
        subtitle_text=extra.get("subtitle_text"),
        character_refs=extra.get("character_refs") or [],
        scene_refs=extra.get("scene_refs") or [],
        prop_refs=extra.get("prop_refs") or [],
        event_refs=extra.get("event_refs") or [],
        environment_context=extra.get("environment_context"),
        character_multiview_refs=extra.get("character_multiview_refs") or consistency.get("character_multiview_refs") or [],
        consistency=consistency,
        seed=seed,
        source_prompt=extra.get("source_prompt"),
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _build_video_generate_response(
    *,
    task_id: str,
    job: VideoJob,
    status_value: str,
    message: str,
) -> VideoGenerateResponse:
    extra = json_dict(job.extra_data)
    return VideoGenerateResponse(
        task_id=task_id,
        job_id=job.id,
        status=status_value,
        message=message,
        project_id=job.project_id or extra.get("project_id"),
        workflow_id=job.workflow_id or extra.get("workflow_id"),
        novel_id=extra.get("novel_id"),
        chapter_id=extra.get("chapter_id"),
        script_id=extra.get("script_id"),
        storyboard_id=extra.get("storyboard_id"),
        shot_id=extra.get("shot_id"),
    )


def _video_job_matches_lineage(job: VideoJob, filters: dict[str, Optional[str]]) -> bool:
    extra = json_dict(job.extra_data)
    for key, value in filters.items():
        if value and extra.get(key) != value:
            return False
    return True


async def _attach_video_job_to_workflow(db: AsyncSession, job: VideoJob, user_id: str) -> None:
    if not job.workflow_id:
        return
    from app.models import Workflow

    workflow_result = await db.execute(
        select(Workflow).where(Workflow.id == job.workflow_id, Workflow.user_id == user_id)
    )
    workflow = workflow_result.scalar_one_or_none()
    if workflow:
        workflow.video_job_ids = list(dict.fromkeys((workflow.video_job_ids or []) + [job.id]))


@router.get("/models")
async def list_video_models(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Return the planned video model catalog merged with the user's configs."""
    from app.api.v1.endpoints.llm_config import ensure_default_models, ensure_default_providers
    from app.models import LLMConfig, LLMModel, LLMProvider

    await ensure_default_providers(db)
    await ensure_default_models(db)

    catalog = get_video_model_catalog("shot_video")
    model_ids = {model["id"] for model in catalog["models"]}
    api_model_ids = {model["api_model_id"] for model in catalog["models"]}

    config_result = await db.execute(
        select(LLMConfig, LLMModel, LLMProvider)
        .join(LLMModel, LLMConfig.model_id == LLMModel.id)
        .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
        .where(
            and_(
                LLMConfig.user_id == user_id,
                LLMConfig.is_active == True,
                LLMModel.is_active == True,
                LLMProvider.is_active == True,
                or_(LLMModel.id.in_(model_ids), LLMModel.model_id.in_(api_model_ids)),
            )
        )
        .order_by(desc(LLMConfig.is_default), desc(LLMConfig.updated_at), desc(LLMConfig.created_at))
    )
    configs_by_key: dict[str, tuple[Any, Any, Any]] = {}
    for config, model, provider in config_result.all():
        for key in (model.id, model.model_id):
            configs_by_key.setdefault(key, (config, model, provider))

    models = []
    for model in catalog["models"]:
        provider = get_provider(model["provider_id"]) or {}
        config_row = configs_by_key.get(model["id"]) or configs_by_key.get(model["api_model_id"])
        config = config_model = config_provider = None
        if config_row:
            config, config_model, config_provider = config_row
        test_status = config.test_status if config else None
        test_message = config.test_message if config else None
        key_available = bool(config and config.get_api_key_decrypted())
        if config and not key_available:
            test_status = "failed"
            test_message = "API Key 为空或无法解密，请重新保存并验证该配置"
        provider_id = (config_provider.name if config_provider else None) or model["provider_id"]
        adapter_status = "available" if provider_id in ARK_VIDEO_PROVIDER_IDS else "planned"
        models.append({
            "id": model["id"],
            "name": model["display_name"],
            "name_cn": model["display_name"],
            "display_name": model["display_name"],
            "provider_id": provider_id,
            "provider_name": (config_provider.name_cn if config_provider else None) or provider.get("display_name") or provider_id,
            "api_model_id": model["api_model_id"],
            "model_id": model["api_model_id"],
            "config_model_id": config_model.id if config_model else model["id"],
            "config_id": config.id if config else None,
            "model_config_id": config.id if config else None,
            "model_type": "video-generation",
            "model_capabilities": model.get("capabilities") or [],
            "capabilities": model.get("capabilities") or [],
            "desc": f"{provider.get('display_name') or provider_id} · {model.get('routing', {}).get('lane', 'catalog')}",
            "limits": model.get("limits") or {},
            "protocol": model.get("protocol") or {},
            "lane": model.get("routing", {}).get("lane", "catalog"),
            "adapter_status": adapter_status,
            "is_configured": bool(config),
            "is_default": bool(config and config.is_default),
            "test_status": test_status,
            "test_message": test_message,
            "key_available": key_available,
        })

    return {
        "task": catalog["task"],
        "display_name": catalog.get("display_name"),
        "required_capabilities": catalog.get("required_capabilities") or [],
        "default_model_id": catalog["default_model_id"],
        "models": models,
    }


@router.post("/generate", response_model=VideoGenerateResponse)
async def generate_video(
    request: VideoGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    生成视频 - 异步提交任务

    使用火山引擎官方SDK调用视频生成API
    """
    try:
        lineage = await resolve_video_lineage(db, user_id, request)
        request = request.model_copy(update={
            "project_id": lineage.get("project_id"),
            "workflow_id": lineage.get("workflow_id"),
            "novel_id": lineage.get("novel_id"),
            "chapter_id": lineage.get("chapter_id"),
            "script_id": lineage.get("script_id"),
            "storyboard_id": lineage.get("storyboard_id"),
            "shot_id": lineage.get("shot_id"),
        })
        video_model_config = await resolve_video_model_config(db, user_id, request.model, request.model_config_id)
        selected_video_model_id = (
            video_model_config.get("api_model")
            or video_model_config.get("api_model_id")
            or video_model_config.get("model_id")
            or video_model_config.get("config_model_id")
            or request.model
        )
        selected_video_provider = (
            video_model_config.get("provider")
            or video_model_config.get("provider_id")
            or video_model_config.get("provider_name")
        )
        real_adapter_available = video_model_config.get("provider_id") in ARK_VIDEO_PROVIDER_IDS or has_video_generation_driver(video_model_config.get("generation_context"))
        if not real_adapter_available and not is_dev_mode():
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=(
                    f"{video_model_config.get('provider_name') or video_model_config.get('provider_id')} "
                    "视频模型已进入目录和配置体系，但真实提交适配器尚未接入。"
                ),
            )
        video_reference_limits = apply_seedance_contract_limits(
            get_model_reference_limits(
                video_model_config.get("api_model_id")
                or video_model_config.get("config_model_id")
                or request.model
            ),
            model_id=selected_video_model_id,
            provider=selected_video_provider,
        )
        if not is_dev_mode() and not request.use_consistency_context and not request.unsafe_skip_consistency_preflight:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="生产模式不能跳过一致性预检；如需降级调试，请显式开启 unsafe_skip_consistency_preflight 并记录原因。",
            )

        final_prompt = request.prompt
        consistency_metadata = {}
        shot_context = extract_shot_generation_context(lineage.get("shot"))
        effective_image_url = request.image_url or getattr(lineage.get("shot"), "image_url", None)
        reference_image_source = "request" if request.image_url else None
        reference_package = None
        if effective_image_url and reference_image_source is None:
            reference_image_source = "shot_image"
        preflight_package = None
        if request.use_consistency_context:
            try:
                package = await build_video_consistency_package(
                    VideoConsistencyPackageContext(db, user_id, request, lineage)
                )
            except VideoConsistencyPackageError as exc:
                raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
            final_prompt = package["final_prompt"]
            consistency_metadata = package["metadata"]
            shot_context = package["context"]
            effective_image_url = package["reference_image"]
            reference_image_source = package["reference_image_source"]
            if video_reference_limits.get("images", 1) > 1 and lineage.get("shot") is not None:
                reference_package = await build_reference_package(
                    db,
                    user_id,
                    shot=lineage["shot"],
                    lineage=lineage,
                    model_limits=video_reference_limits,
                    resolve_public_url=resolve_provider_image_delivery,
                )
                reference_package = await bind_reference_package(
                    db,
                    reference_package,
                    provider_id=str(selected_video_provider or "volcano"),
                    model_id=str(selected_video_model_id or request.model),
                    allow_canonical_public_fallback=True,
                )
                effective_image_url = reference_package.get("reference_image") or effective_image_url
                reference_image_source = reference_package.get("reference_image_source") or reference_image_source
        if not is_dev_mode():
            preflight_package = await build_generation_context_package(
                db,
                user_id,
                task_type="shot_video",
                model_config_id=video_model_config.get("model_config_id"),
                image_url=effective_image_url,
                production_mode=True,
                require_public_reference_image=bool(effective_image_url),
                novel_id=request.novel_id,
                chapter_id=request.chapter_id,
                script_id=request.script_id,
                storyboard_id=request.storyboard_id,
                shot_id=request.shot_id,
            )
            if not preflight_package.get("ready"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail={
                        "code": "generation_preflight_failed",
                        "message": "生成预检未通过，请先处理阻断项或明确选择降级策略。",
                        "issues": preflight_package.get("issues") or [],
                        "blocking_issue_count": preflight_package.get("blocking_issue_count") or 0,
                        "autofix_actions": preflight_package.get("autofix_actions") or [],
                    },
                )
        video_seed = resolve_video_seed(request, lineage, consistency_metadata)
        image_delivery = await resolve_provider_image_delivery(db, user_id, effective_image_url)
        provider_image_url = image_delivery["provider_image_url"]
        image_url_omitted_reason = image_delivery["image_url_omitted_reason"]
        if image_url_omitted_reason:
            final_prompt = append_provider_image_note(final_prompt, image_url_omitted_reason)
        provider_prompt = sanitize_provider_video_prompt(final_prompt)
        provider_final_prompt = provider_prompt["prompt"]
        context_metadata = build_video_context_metadata(lineage, consistency_metadata, video_seed, shot_context)
        if preflight_package is not None:
            context_metadata["generation_preflight"] = {
                "ready": preflight_package.get("ready"),
                "issues": preflight_package.get("issues") or [],
                "blocking_issue_count": preflight_package.get("blocking_issue_count") or 0,
            }
        prompt_parameters = video_prompt_parameters(
            request.model_copy(update={"image_url": effective_image_url}),
            video_seed,
            provider_image_url,
            image_url_omitted_reason,
            image_delivery["image_delivery"],
        )
        prompt_parameters["reference_image_source"] = reference_image_source
        supplemental_refs = shot_context.get("character_multiview_refs") or []
        prompt_parameters["provider_reference_image_limit"] = video_reference_limits["images"]
        prompt_parameters["reference_image_strategy"] = (
            "single_provider_image_with_textual_asset_constraints"
            if supplemental_refs or (shot_context.get("asset_version_locks") or [])
            else "single_provider_image"
        )
        prompt_parameters["supplemental_reference_image_count"] = len(supplemental_refs)
        if provider_prompt["sanitized"]:
            prompt_parameters["provider_prompt_sanitized"] = True
            prompt_parameters["provider_prompt_replacements"] = provider_prompt["replacements"]
        provider_content = build_video_provider_content(
            final_prompt=provider_final_prompt,
            duration=request.duration,
            resolution=request.resolution,
            provider_image_url=provider_image_url,
            reference_package=reference_package,
            model_limits=video_reference_limits,
            model_id=selected_video_model_id,
            provider=selected_video_provider,
            camera_fixed=False,
            watermark=PROVIDER_VIDEO_WATERMARK_ENABLED,
        )
        provider_metadata = provider_content["metadata"]
        model_protocol = video_model_config.get("protocol") if isinstance(video_model_config.get("protocol"), dict) else {}
        prompt_parameters = enrich_prompt_parameters_with_reference_contract(
            prompt_parameters,
            provider_metadata,
            video_reference_limits,
            model_protocol,
        )
        if provider_content["mode"] == "multimodal":
            prompt_parameters["reference_image_strategy"] = "multimodal_reference_package"
        reference_package_metadata = build_reference_package_metadata(
            reference_package,
            provider_content["metadata"],
        )

        # 使用请求提供的 API key、所选视频模型配置或同 provider 的可用 Key。
        if request.api_key:
            resolved_api_key = request.api_key
            resolved_base_url = video_model_config.get("base_url")
        else:
            resolved_api_key = video_model_config.get("api_key")
            resolved_base_url = video_model_config.get("base_url")
            if not resolved_api_key:
                resolved_api_key, fallback_base_url = await get_user_api_key(
                    db,
                    user_id,
                    video_model_config.get("provider_id") or "volcano",
                    raise_if_missing=False,
                )
                resolved_base_url = resolved_base_url or fallback_base_url

        if is_dev_mode() and (not resolved_api_key or not real_adapter_available):
            job_id = str(uuid4())
            task_id = f"dev-video-{job_id}"
            video_url = dev_video_url(job_id, duration_seconds=request.duration)
            extra_data = build_video_extra_data(request, lineage)
            extra_data.update(context_metadata)
            extra_data.update(video_model_metadata(video_model_config))
            extra_data["prompt_parameters"] = prompt_parameters
            extra_data["reference_package"] = reference_package_metadata
            extra_data["source_prompt"] = request.prompt
            job = VideoJob(
                id=job_id,
                user_id=user_id,
                project_id=request.project_id,
                workflow_id=request.workflow_id,
                task_id=task_id,
                title=request.prompt[:50] if len(request.prompt) > 50 else request.prompt,
                prompt=provider_final_prompt,
                model_id=video_model_config.get("api_model_id") or request.model,
                model_name=f"{video_model_config.get('model_name') or get_video_model_name(request.model)} (DEV_MODE)",
                duration=request.duration,
                resolution=request.resolution,
                image_url=effective_image_url,
                status="succeeded",
                progress=100,
                video_url=video_url,
                cover_url=None,
                extra_data=extra_data,
            )
            db.add(job)
            await _attach_video_job_to_workflow(db, job, user_id)
            await sync_video_job_and_shot(
                db, job, VideoJobSyncCommand("succeeded", 100, video_url, None),
            )
            await db.commit()

            await log_activity(
                db=db,
                user_id=user_id,
                activity_type="created",
                entity_type="video",
                entity_id=job.id,
                title=f"DEV_MODE 视频任务完成: {job.title}",
            )
            await db.commit()

            return _build_video_generate_response(
                task_id=task_id,
                job=job,
                status_value="succeeded",
                message="DEV_MODE 本地视频任务已完成，未调用云端视频模型",
            )

        if not resolved_api_key:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"未配置 {video_model_config.get('provider_name') or video_model_config.get('provider_id') or '视频模型'} API Key，请在 LLM 配置页面配置并测试视频模型"
            )
        client = create_ark_client(resolved_api_key, resolved_base_url)

        # 视频模型需要 endpoint_id，不是模型名。
        video_model = video_model_config.get("model_endpoint_id") or request.model

        # 调用SDK创建任务
        create_kwargs = build_ark_video_create_kwargs(
            model=video_model, content=provider_content["content"], duration=request.duration,
            resolution=request.resolution, camera_fixed=False,
            watermark=PROVIDER_VIDEO_WATERMARK_ENABLED, seed=video_seed,
        )
        try:
            create_result = await submit_bound_video_task(video_model_config.get("generation_context"), provider_final_prompt, create_kwargs, client)
        except Exception as exc:
            image_error = provider_image_url_error_message(exc, provider_image_url)
            if image_error:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=image_error) from exc
            text_error = provider_text_safety_error_message(exc)
            if text_error:
                fallback_prompt = build_provider_video_prompt_fallback()
                fallback_content = build_video_provider_content(
                    final_prompt=fallback_prompt["prompt"],
                    duration=request.duration,
                    resolution=request.resolution,
                    provider_image_url=provider_image_url,
                    reference_package=reference_package,
                    model_limits=video_reference_limits,
                    model_id=selected_video_model_id,
                    provider=selected_video_provider,
                    camera_fixed=False,
                    watermark=PROVIDER_VIDEO_WATERMARK_ENABLED,
                )
                retry_kwargs = {**create_kwargs, "content": fallback_content["content"]}
                try:
                    create_result = await submit_bound_video_task(video_model_config.get("generation_context"), fallback_prompt["prompt"], retry_kwargs, client)
                except Exception as retry_exc:
                    retry_image_error = provider_image_url_error_message(retry_exc, provider_image_url)
                    if retry_image_error:
                        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=retry_image_error) from retry_exc
                    retry_text_error = provider_text_safety_error_message(retry_exc)
                    if retry_text_error:
                        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=retry_text_error) from retry_exc
                    raise
                provider_final_prompt = fallback_prompt["prompt"]
                provider_content = fallback_content
                provider_metadata = provider_content["metadata"]
                prompt_parameters["provider_prompt_safety_retry"] = True
                prompt_parameters["provider_prompt_safety_retry_reason"] = "InputTextSensitiveContentDetected"
                prompt_parameters["provider_prompt_fallback_replacements"] = fallback_prompt["replacements"]
                prompt_parameters = enrich_prompt_parameters_with_reference_contract(
                    prompt_parameters,
                    provider_metadata,
                    video_reference_limits,
                    model_protocol,
                )
                reference_package_metadata = build_reference_package_metadata(
                    reference_package,
                    provider_content["metadata"],
                )
            else:
                raise

        # 构建关联数据（ID + 标题）
        extra_data = build_video_extra_data(request, lineage)
        extra_data.update(context_metadata)
        extra_data.update(video_model_metadata(video_model_config))
        extra_data["prompt_parameters"] = prompt_parameters
        extra_data["reference_package"] = reference_package_metadata
        extra_data["source_prompt"] = request.prompt

        # 创建数据库记录
        job = VideoJob(
            id=str(uuid4()),
            user_id=user_id,
            project_id=request.project_id,
            workflow_id=request.workflow_id,
            task_id=create_result.id,
            title=request.prompt[:50] if len(request.prompt) > 50 else request.prompt,
            prompt=provider_final_prompt,
            model_id=video_model_config.get("api_model_id") or request.model,
            model_name=video_model_config.get("model_name") or get_video_model_name(request.model),
            duration=request.duration,
            resolution=request.resolution,
            image_url=effective_image_url,
            status="pending",
            progress=10,
            extra_data=extra_data,
        )
        db.add(job)
        await _attach_video_job_to_workflow(db, job, user_id)
        await db.commit()

        await log_activity(
            db=db,
            user_id=user_id,
            activity_type="created",
            entity_type="video",
            entity_id=job.id,
            title=f"提交视频生成: {job.title}",
        )
        await db.commit()

        return _build_video_generate_response(
            task_id=create_result.id,
            job=job,
            status_value="pending",
            message="视频生成任务已提交，请使用task_id查询状态",
        )

    except VideoGenerationError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"视频生成失败: {str(e)}"
        )


@router.get("/status/{task_id}", response_model=VideoStatusResponse)
async def get_video_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    api_key: Optional[str] = None
):
    """
    查询视频生成状态。

    使用 task_id 轮询任务状态。API Key 优先使用请求参数，
    否则从用户的 LLMConfig 中获取。
    """
    job_result = await db.execute(
        select(VideoJob).where(VideoJob.task_id == task_id, VideoJob.user_id == user_id)
    )
    existing_job = job_result.scalar_one_or_none()
    if existing_job and (task_id.startswith("dev-video-") or existing_job.status in {"succeeded", "failed"}):
        return VideoStatusResponse(
            task_id=task_id,
            job_id=existing_job.id,
            status=existing_job.status,
            video_url=existing_job.video_url,
            cover_url=existing_job.cover_url,
            message="视频生成完成" if existing_job.status == "succeeded" else (existing_job.error_message or "视频生成失败"),
            progress=existing_job.progress,
            duration=existing_job.duration,
            resolution=existing_job.resolution
        )

    provider_for_status = "volcano"
    if existing_job:
        provider_for_status = (json_dict(existing_job.extra_data).get("provider_id") or "volcano")

    if api_key:
        resolved_api_key = api_key
        resolved_base_url = None
    else:
        resolved_api_key, resolved_base_url = await get_user_api_key(
            db, user_id, provider_for_status, raise_if_missing=False
        )
    if not resolved_api_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"未配置 {provider_for_status} API Key，请在设置页面配置"
        )

    try:
        client = create_ark_client(resolved_api_key, resolved_base_url)
        
        get_result = client.content_generation.tasks.get(task_id=task_id)
        task_status = get_result.status
        
        # 状态映射
        status_map = {
            "pending": "pending",
            "running": "running", 
            "succeeded": "succeeded",
            "failed": "failed"
        }
        
        mapped_status = status_map.get(task_status, task_status)
        
        # 获取输出信息
        video_url = None
        cover_url = None
        duration = None
        resolution = None
        progress = None
        
        if task_status == "succeeded":
            video_url, cover_url = _extract_video_result(get_result)
        
        if hasattr(get_result, 'duration'):
            duration = get_result.duration
        if hasattr(get_result, 'resolution'):
            resolution = get_result.resolution
        
        # 进度百分比估算
        if task_status == "pending":
            progress = 10
        elif task_status == "running":
            progress = 50
        elif task_status == "succeeded":
            progress = 100
        
        message = {
            "pending": "任务等待中",
            "running": "视频生成中，请稍候",
            "succeeded": "视频生成完成",
            "failed": f"生成失败: {getattr(get_result, 'error', 'Unknown error')}"
        }.get(task_status, f"未知状态: {task_status}")
        
        job_record = existing_job
        job_id = job_record.id if job_record else None
        if job_record:
            accounting = json_dict(job_record.extra_data).get("live_canary_accounting") or {}
            if accounting.get("operation_id"):
                await settle_provider_operation(
                    db, operation_id=accounting["operation_id"], user_id=user_id,
                    run_id=accounting["series_run_id"], reservation_id=accounting["reservation_id"],
                    capability="video", job_id=job_record.id, provider_task_id=task_id,
                    provider_status=mapped_status,
                    actual_rmb=getattr(get_result, "actual_cost_rmb", getattr(get_result, "cost_rmb", None)),
                )
            await sync_video_job_and_shot(
                db, job_record, VideoJobSyncCommand(
                    mapped_status, progress, video_url, cover_url,
                    str(getattr(get_result, "error", "")) if mapped_status == "failed" else None,
                ),
            )
            await db.commit()

        return VideoStatusResponse(
            task_id=task_id,
            job_id=job_id,
            status=mapped_status,
            video_url=video_url,
            cover_url=cover_url,
            message=message,
            progress=progress,
            duration=duration,
            resolution=resolution
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询状态失败: {str(e)}"
        )


@router.get("/jobs", response_model=List[VideoJobResponse])
async def list_video_jobs(
    project_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    novel_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    script_id: Optional[str] = None,
    storyboard_id: Optional[str] = None,
    shot_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    获取用户的视频任务历史列表
    """
    query = select(VideoJob).where(
        VideoJob.user_id == user_id,
        VideoJob.is_active == True
    )
    if project_id:
        query = query.where(VideoJob.project_id == project_id)
    if workflow_id:
        query = query.where(VideoJob.workflow_id == workflow_id)
    needs_lineage_filter = any([novel_id, chapter_id, script_id, storyboard_id, shot_id])
    query = query.order_by(desc(VideoJob.created_at)).limit(200 if needs_lineage_filter else 50)
    result = await db.execute(query)
    jobs = result.scalars().all()
    if needs_lineage_filter:
        filters = {
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": script_id,
            "storyboard_id": storyboard_id,
            "shot_id": shot_id,
        }
        jobs = [job for job in jobs if _video_job_matches_lineage(job, filters)][:50]

    return [_build_video_job_response(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=VideoJobResponse)
async def get_video_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    获取单个视频任务详情
    """
    result = await db.execute(
        select(VideoJob).where(
            VideoJob.id == job_id,
            VideoJob.user_id == user_id
        )
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    return _build_video_job_response(job)


@router.post("/jobs/{job_id}/refresh")
async def refresh_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    刷新任务状态（从第三方API获取最新状态并更新数据库）
    """
    result = await db.execute(
        select(VideoJob).where(
            VideoJob.id == job_id,
            VideoJob.user_id == user_id
        )
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    if not job.task_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务没有第三方task_id"
        )
    
    try:
        # 从用户的 LLMConfig 获取 API 密钥
        resolved_api_key, resolved_base_url = await resolve_video_job_client_config(
            db, user_id, job,
        )
        client = create_ark_client(resolved_api_key, resolved_base_url)
        
        get_result = client.content_generation.tasks.get(task_id=job.task_id)
        task_status = get_result.status
        accounting = json_dict(job.extra_data).get("live_canary_accounting") or {}
        if accounting.get("operation_id"):
            await settle_provider_operation(
                db, operation_id=accounting["operation_id"], user_id=user_id,
                run_id=accounting["series_run_id"], reservation_id=accounting["reservation_id"],
                capability="video", job_id=job.id, provider_task_id=job.task_id,
                provider_status=task_status,
                actual_rmb=getattr(get_result, "actual_cost_rmb", getattr(get_result, "cost_rmb", None)),
            )
        
        # 更新状态
        job.status = task_status
        
        if task_status == "succeeded":
            job.progress = 100
            video_url, cover_url = _extract_video_result(get_result)
            await sync_video_job_and_shot(
                db, job, VideoJobSyncCommand(task_status, 100, video_url, cover_url),
            )
            # Log completion activity (commit happens below with job update)
            await log_activity(
                db=db,
                user_id=job.user_id,
                activity_type="completed",
                entity_type="video",
                entity_id=job.id,
                title=f"视频生成完成: {job.title}",
                description="视频生成任务已成功完成",
            )
        elif task_status == "running":
            await sync_video_job_and_shot(db, job, VideoJobSyncCommand(task_status, 50, None, None))
        elif task_status == "failed":
            await sync_video_job_and_shot(
                db, job, VideoJobSyncCommand(
                    task_status, 100, None, None, str(getattr(get_result, 'error', 'Unknown error')),
                ),
            )
        
        await db.commit()
        
        return {
            "id": job.id,
            "status": job.status,
            "progress": job.progress,
            "video_url": job.video_url,
            "message": "状态已更新"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"刷新状态失败: {str(e)}"
        )


@router.put("/jobs/{job_id}", response_model=VideoJobResponse)
async def update_video_job(
    job_id: str,
    request: VideoJobUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """更新视频任务元数据，用于取消、归档前的状态调整和任务中心管理。"""
    result = await db.execute(
        select(VideoJob).where(VideoJob.id == job_id, VideoJob.user_id == user_id, VideoJob.is_active == True)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    if request.status is not None:
        if request.status not in {"pending", "running", "succeeded", "completed", "failed", "cancelled", "archived"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="不支持的视频任务状态")
        job.status = request.status
    if request.progress is not None:
        job.progress = request.progress
    if request.title is not None:
        job.title = request.title
    if request.error_message is not None:
        job.error_message = request.error_message
    job.updated_at = utc_now()

    if job.status in {"cancelled", "failed"}:
        await sync_video_job_and_shot(
            db, job, VideoJobSyncCommand(job.status, job.progress or 0, None, None, job.error_message),
        )

    await db.commit()
    await db.refresh(job)
    return _build_video_job_response(job)


@router.post("/jobs/{job_id}/cancel", response_model=VideoJobResponse)
async def cancel_video_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """取消本地跟踪的视频任务。第三方任务取消能力由后续供应商适配器实现。"""
    result = await db.execute(
        select(VideoJob).where(VideoJob.id == job_id, VideoJob.user_id == user_id, VideoJob.is_active == True)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    if job.status in {"succeeded", "completed"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已完成任务不能取消")

    job.status = "cancelled"
    job.progress = job.progress or 0
    job.error_message = job.error_message or "任务已由用户取消"
    job.updated_at = utc_now()
    await sync_video_job_and_shot(
        db, job, VideoJobSyncCommand("cancelled", job.progress, None, None, job.error_message),
    )
    await db.commit()
    await db.refresh(job)
    return _build_video_job_response(job)


@router.delete("/jobs/{job_id}")
async def delete_video_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """软删除视频任务，保留数据库记录用于审计和恢复。"""
    result = await db.execute(
        select(VideoJob).where(VideoJob.id == job_id, VideoJob.user_id == user_id, VideoJob.is_active == True)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    job.is_active = False
    job.status = "archived"
    job.updated_at = utc_now()
    await db.commit()
    return {"message": "视频任务已归档", "job_id": job_id}


# ============== 废弃的旧API（保持向后兼容）==============

class OldVideoGenerateRequest(BaseModel):
    """旧版视频生成请求（兼容）"""
    prompt: str
    api_key: str
    duration: int = 5
    image_url: Optional[str] = None


@router.post("/generate/legacy")
async def generate_video_legacy(
    request: OldVideoGenerateRequest
):
    """
    旧版视频生成接口（已废弃）。

    此接口仅用于向后兼容。不推荐在新代码中使用。
    请使用 /video/generate 接口，并通过用户的 LLMConfig 配置 API Key。
    """
    new_request = VideoGenerateRequest(
        prompt=request.prompt,
        duration=request.duration,
        api_key=request.api_key,
        image_url=request.image_url
    )
    # legacy endpoint 无法获取 user_id，跳过 LLMConfig 查找
    # 仅在明确提供了 api_key 时工作
    if not new_request.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Legacy 接口需要提供 api_key（请改用新版 /video/generate 接口）"
        )
    return await generate_video(new_request)


# ============== 视频下载代理接口 ==============

class VideoDownloadRequest(BaseModel):
    """视频下载请求"""
    video_url: str = Field(..., description="视频URL")
    filename: Optional[str] = Field(None, description="下载文件名")


def _safe_download_filename(filename: Optional[str]) -> str:
    value = (filename or "video.mp4").strip() or "video.mp4"
    value = value.replace("/", "_").replace("\\", "_").replace('"', "")
    return value if value.lower().endswith(".mp4") else f"{value}.mp4"


def _local_static_file_for_media_url(media_url: str, request_netloc: str) -> Optional[Path]:
    import urllib.parse

    parsed = urllib.parse.urlparse(media_url)
    if parsed.netloc and parsed.netloc != request_netloc:
        return None
    media_path = urllib.parse.unquote(parsed.path or media_url)
    if not media_path.startswith("/static/"):
        return None
    relative = media_path.removeprefix("/static/").lstrip("/")
    candidate = (STATIC_ROOT / relative).resolve()
    try:
        candidate.relative_to(STATIC_ROOT.resolve())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的本地静态资源路径")
    return candidate


@router.post("/download")
async def download_video(
    request: VideoDownloadRequest,
    http_request: Request,
):
    """
    代理下载视频 - 解决URL特殊字符截断问题
    
    由于火山引擎视频URL包含特殊字符，前端直接打开可能截断
    因此通过后端代理下载
    """
    try:
        import httpx
        import urllib.parse
        from fastapi.responses import FileResponse, Response
        
        video_url = request.video_url

        filename = _safe_download_filename(request.filename)
        local_file = _local_static_file_for_media_url(video_url, http_request.url.netloc)
        if local_file is not None:
            if not local_file.exists():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="本地视频文件不存在")
            return FileResponse(local_file, media_type="video/mp4", filename=filename)

        parsed = urllib.parse.urlparse(video_url)
        if not parsed.scheme:
            video_url = urllib.parse.urljoin(str(http_request.base_url), video_url)

        # 使用httpx下载视频
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(video_url)
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"下载失败: HTTP {response.status_code}"
                )

            headers = {
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "video/mp4",
            }
            return Response(content=response.content, media_type="video/mp4", headers=headers)
            
    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="下载超时，请稍后重试"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下载失败: {str(e)}"
        )
