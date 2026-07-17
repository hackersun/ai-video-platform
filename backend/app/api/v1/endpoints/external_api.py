"""
External production capability configuration.

This endpoint group is the unified management surface for optional production
adapters: Sora/Veo style audio-video generation, ComfyUI workflow execution,
FFmpeg/cloud rendering, lip-sync services and other plugin-style providers.
"""

from __future__ import annotations
from app.core.time_utils import utc_now

import shutil
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dev_generation import is_dev_mode
from app.core.model_registry import get_registry
from app.core.qwen_config import QWEN_MODELS
from app.core.security import get_current_user_id
from app.features.model_config.public import (
    build_legacy_external_provider_response,
    select_legacy_external_providers,
)
from app.models.external_api import ExternalAPIConfig, ExternalAPIProvider
from app.services.media_delivery import resolve_provider_media_url
from app.services.media_persistence import STATIC_ROOT

router = APIRouter(tags=["外部API"])


DEFAULT_PROVIDERS: List[Dict[str, Any]] = [
    {
        "id": "openai",
        "name": "openai",
        "name_cn": "OpenAI / Sora",
        "api_type": "audio_video",
        "base_url": "https://api.openai.com/v1",
        "auth_type": "bearer",
        "description": "Sora 类文本/图像到音视频生成适配。实际提交路径可在 extra_config.submit_path 中配置。",
        "doc_url": "https://platform.openai.com/docs",
        "supported_models": [
            {
                "id": "openai.sora_2",
                "name": "Sora 2",
                "capabilities": ["text_to_audio_video", "image_to_audio_video", "dialogue_audio", "subtitle_timing"],
            }
        ],
    },
    {
        "id": "google",
        "name": "google",
        "name_cn": "Google Veo",
        "api_type": "audio_video",
        "base_url": "https://aiplatform.googleapis.com",
        "auth_type": "bearer",
        "description": "Veo 类文本/图像到视频生成适配，支持通过自定义提交路径对接 Vertex AI 或代理服务。",
        "doc_url": "https://cloud.google.com/vertex-ai/generative-ai/docs/video/generate-videos",
        "supported_models": [
            {
                "id": "google.veo_3",
                "name": "Veo 3",
                "capabilities": ["text_to_audio_video", "image_to_audio_video", "dialogue_audio", "sound_effect_generation"],
            }
        ],
    },
    {
        "id": "comfyui",
        "name": "comfyui",
        "name_cn": "ComfyUI",
        "api_type": "workflow",
        "base_url": "http://127.0.0.1:8188",
        "auth_type": "none",
        "description": "ComfyUI 工作流 JSON 适配，可映射 ControlNet、IP-Adapter、AnimateDiff 等节点参数。",
        "doc_url": "https://docs.comfy.org/",
        "supported_models": [
            {
                "id": "comfyui.workflow_adapter",
                "name": "ComfyUI Workflow Adapter",
                "capabilities": ["workflow_json", "controlnet", "ip_adapter", "animatediff", "multi_reference"],
            }
        ],
    },
    {
        "id": "ffmpeg_cloud",
        "name": "ffmpeg_cloud",
        "name_cn": "FFmpeg 云渲染",
        "api_type": "render",
        "base_url": "",
        "auth_type": "bearer",
        "description": "远端 FFmpeg/云剪辑渲染执行器，消费 workflow render manifest、SRT 和 timeline。",
        "doc_url": "https://ffmpeg.org/documentation.html",
        "supported_models": [
            {
                "id": "ffmpeg.cloud_renderer",
                "name": "FFmpeg Cloud Renderer",
                "capabilities": ["audio_video_mux", "subtitle_burn_in", "timeline_render", "render_package"],
            }
        ],
    },
    {
        "id": "local_ffmpeg",
        "name": "local_ffmpeg",
        "name_cn": "本地 FFmpeg",
        "api_type": "render",
        "base_url": "",
        "auth_type": "none",
        "description": "本机 FFmpeg 执行器，用于真实转码、混音和字幕烧录的本地适配。",
        "doc_url": "https://ffmpeg.org/documentation.html",
        "supported_models": [
            {
                "id": "local.ffmpeg",
                "name": "Local FFmpeg",
                "capabilities": ["audio_video_mux", "subtitle_burn_in", "timeline_render"],
            }
        ],
    },
    {
        "id": "lip_sync",
        "name": "lip_sync",
        "name_cn": "口型/唇形适配",
        "api_type": "lip_sync",
        "base_url": "",
        "auth_type": "bearer",
        "description": "可对接 HeyGen、Wav2Lip、Live2D 或自建口型服务，按镜头音频驱动角色口型。",
        "supported_models": [
            {
                "id": "generic.lip_sync",
                "name": "Generic Lip Sync Adapter",
                "capabilities": ["lip_sync", "audio_driven_video", "avatar_animation"],
            }
        ],
    },
    {
        "id": "object_storage",
        "name": "object_storage",
        "name_cn": "对象存储 / CDN",
        "api_type": "storage",
        "base_url": "",
        "auth_type": "none",
        "description": "为角色头像、镜头参考图、资产参考图提供公网访问出口，云端图生视频会优先使用该配置。",
        "supported_models": [
            {
                "id": "storage.public_static",
                "name": "公开静态媒体出口",
                "capabilities": ["public_reference_image", "static_url_mapping", "cdn_delivery"],
            },
            {
                "id": "storage.object_upload",
                "name": "对象存储上传预留",
                "capabilities": ["s3_compatible", "minio", "oss", "signed_url"],
            },
        ],
    },
    {
        "id": "runway",
        "name": "runway",
        "name_cn": "Runway",
        "api_type": "video",
        "base_url": "https://api.runwayml.com/v1",
        "auth_type": "bearer",
        "description": "AI 视频生成和参考图工作流适配。",
        "supported_models": [{"id": "runway.gen4", "name": "Runway Gen-4", "capabilities": ["video_generation", "references"]}],
    },
    {
        "id": "qwen",
        "name": "qwen",
        "name_cn": "阿里千问",
        "api_type": "text",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "auth_type": "bearer",
        "description": "阿里通义千问大模型",
        "supported_models": [{"id": m["id"], "name": m["name_cn"]} for m in QWEN_MODELS],
    },
]


class ExternalAPIProviderResponse(BaseModel):
    id: str
    name: str
    name_cn: Optional[str]
    api_type: str
    base_url: str
    auth_type: str
    is_active: bool
    description: Optional[str]
    doc_url: Optional[str] = None
    supported_models: List[dict] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)


class ExternalAPIConfigCreateRequest(BaseModel):
    provider_id: str = Field(..., description="提供商ID")
    name: str = Field(..., min_length=1, max_length=100, description="配置名称")
    api_key: Optional[str] = Field(None, description="API密钥；本地执行器可为空")
    api_secret: Optional[str] = Field(None, description="API Secret")
    custom_base_url: Optional[str] = Field(None, description="自定义基础URL")
    timeout: int = Field(60, ge=5, le=600)
    retry_count: int = Field(3, ge=0, le=10)
    description: Optional[str] = Field(None, description="描述")
    extra_config: Dict[str, Any] = Field(default_factory=dict, description="提交路径、健康检查路径、工作流模板等适配参数")
    is_default: bool = Field(False, description="设为该提供商默认")


class ExternalAPIConfigUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    custom_base_url: Optional[str] = None
    timeout: Optional[int] = Field(None, ge=5, le=600)
    retry_count: Optional[int] = Field(None, ge=0, le=10)
    description: Optional[str] = None
    extra_config: Optional[Dict[str, Any]] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class ExternalAPIConfigResponse(BaseModel):
    id: str
    provider_id: str
    provider_name: str
    provider_key: str
    api_type: str
    name: str
    custom_base_url: Optional[str] = None
    timeout: int
    retry_count: int
    is_active: bool
    is_default: bool
    test_status: Optional[str]
    test_message: Optional[str] = None
    tested_at: Optional[datetime] = None
    usage_count: int
    description: Optional[str] = None
    extra_config: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: Optional[datetime] = None


class ExternalAPITestResponse(BaseModel):
    config_id: str
    status: str
    success: bool
    message: str
    checked_at: datetime


class ExternalAPIDeliveryTestResponse(BaseModel):
    config_id: str
    status: str
    success: bool
    message: str
    checked_at: datetime
    source_url: str
    delivery_method: Optional[str] = None
    object_key: Optional[str] = None
    download_status: Optional[int] = None
    provider_url_preview: Optional[str] = None


class ProductionCapabilityStatus(BaseModel):
    providers: List[ExternalAPIProviderResponse]
    configs: List[ExternalAPIConfigResponse]
    readiness: Dict[str, Any]
    registry: Dict[str, Any]


def _config_response(config: ExternalAPIConfig, provider: ExternalAPIProvider) -> ExternalAPIConfigResponse:
    return ExternalAPIConfigResponse(
        id=config.id,
        provider_id=config.provider_id,
        provider_name=provider.name_cn or provider.name,
        provider_key=provider.name,
        api_type=provider.api_type,
        name=config.name,
        custom_base_url=config.custom_base_url,
        timeout=config.timeout or 60,
        retry_count=config.retry_count or 0,
        is_active=bool(config.is_active),
        is_default=bool(config.is_default),
        test_status=config.test_status,
        test_message=config.test_message,
        tested_at=config.tested_at,
        usage_count=config.usage_count or 0,
        description=config.description,
        extra_config=config.extra_config or {},
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


async def _ensure_default_providers(db: AsyncSession) -> List[ExternalAPIProvider]:
    result = await db.execute(select(ExternalAPIProvider))
    existing = {provider.id: provider for provider in result.scalars().all()}
    changed = False
    for item in DEFAULT_PROVIDERS:
        provider = existing.get(item["id"])
        if not provider:
            provider = ExternalAPIProvider(**item)
            db.add(provider)
            existing[item["id"]] = provider
            changed = True
            continue
        for key, value in item.items():
            if getattr(provider, key, None) != value:
                setattr(provider, key, value)
                changed = True
    if changed:
        await db.commit()
    result = await db.execute(select(ExternalAPIProvider).where(ExternalAPIProvider.is_active == True))
    return list(result.scalars().all())


async def _get_provider(db: AsyncSession, provider_id: str) -> ExternalAPIProvider:
    await _ensure_default_providers(db)
    result = await db.execute(select(ExternalAPIProvider).where(ExternalAPIProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="提供商不存在")
    return provider


async def _get_config_with_provider(
    db: AsyncSession,
    user_id: str,
    config_id: str,
) -> tuple[ExternalAPIConfig, ExternalAPIProvider]:
    result = await db.execute(
        select(ExternalAPIConfig, ExternalAPIProvider)
        .join(ExternalAPIProvider, ExternalAPIConfig.provider_id == ExternalAPIProvider.id)
        .where(and_(ExternalAPIConfig.id == config_id, ExternalAPIConfig.user_id == user_id))
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="外部能力配置不存在")
    return row[0], row[1]


async def _unset_default_for_provider(db: AsyncSession, user_id: str, provider_id: str) -> None:
    await db.execute(
        update(ExternalAPIConfig)
        .where(and_(ExternalAPIConfig.user_id == user_id, ExternalAPIConfig.provider_id == provider_id))
        .values(is_default=False)
    )


def _base_url(config: ExternalAPIConfig, provider: ExternalAPIProvider) -> str:
    return (config.custom_base_url or provider.base_url or "").rstrip("/")


def _is_public_http_url(url: str) -> bool:
    from app.services.media_delivery import is_cloud_accessible_http_url

    return is_cloud_accessible_http_url(url)


def _mask_url_for_response(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    parts = urlsplit(url)
    masked_query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower() in {"token", "authorization", "signature", "sign", "x-amz-signature"}:
            masked_query.append((key, "***"))
        else:
            masked_query.append((key, value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(masked_query), parts.fragment))


def _write_delivery_probe_file() -> str:
    target_dir = Path(STATIC_ROOT) / "generated" / "adapter-self-check"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"probe-{uuid4().hex}.png"
    # 1x1 transparent PNG. The self-check validates delivery plumbing, not image quality.
    target_path.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return f"/static/generated/adapter-self-check/{target_path.name}"


async def _test_external_config(config: ExternalAPIConfig, provider: ExternalAPIProvider) -> tuple[str, str]:
    provider_key = provider.name
    extra = config.extra_config or {}
    base_url = _base_url(config, provider)

    if provider_key == "local_ffmpeg":
        binary = extra.get("binary_path") or "ffmpeg"
        if shutil.which(binary):
            return "success", f"本地 FFmpeg 可用：{binary}"
        return "failed", f"未找到本地 FFmpeg 可执行文件：{binary}"

    if provider_key == "comfyui":
        if not base_url:
            return "failed", "ComfyUI 需要配置服务地址"
        health_path = extra.get("health_path") or "/system_stats"
        try:
            async with httpx.AsyncClient(timeout=min(config.timeout or 20, 20)) as client:
                response = await client.get(f"{base_url}{health_path}")
            if response.status_code < 400:
                return "success", "ComfyUI 服务可访问"
            return "failed", f"ComfyUI 健康检查失败：HTTP {response.status_code}"
        except Exception as exc:
            if is_dev_mode():
                return "configured", f"配置已保存，但 DEV_MODE 未连通 ComfyUI：{exc}"
            return "failed", f"ComfyUI 连接失败：{exc}"

    if provider_key in {"ffmpeg_cloud", "lip_sync"} and base_url:
        health_path = extra.get("health_path") or "/health"
        try:
            headers = {}
            api_key = config.get_api_key_decrypted()
            if api_key and provider.auth_type != "none":
                headers[provider.auth_header or "Authorization"] = f"Bearer {api_key}" if provider.auth_type == "bearer" else api_key
            async with httpx.AsyncClient(timeout=min(config.timeout or 20, 20)) as client:
                response = await client.get(f"{base_url}{health_path}", headers=headers)
            if response.status_code < 400:
                return "success", f"{provider.name_cn or provider.name} 服务可访问"
            return "failed", f"健康检查失败：HTTP {response.status_code}"
        except Exception as exc:
            if is_dev_mode():
                return "configured", f"配置已保存，但 DEV_MODE 未连通远端服务：{exc}"
            return "failed", f"连接失败：{exc}"

    if provider_key in {"openai", "google", "runway", "qwen"}:
        if provider.auth_type != "none" and not config.get_api_key_decrypted():
            return "failed", "缺少 API Key"
        if extra.get("validate_live"):
            if not base_url:
                return "failed", "缺少基础 URL"
            return "configured", "已开启真实验证，但该提供商需在提交任务时按具体模型接口验证权限"
        return "configured", "配置完整；真实任务提交时会按供应商接口验证权限和额度"

    if provider_key == "object_storage":
        public_base_url = (extra.get("public_base_url") or base_url).strip()
        if not public_base_url:
            return "failed", "缺少公网基础地址，请填写 CDN/对象存储公开域名"
        if not _is_public_http_url(public_base_url):
            return "failed", "公网基础地址必须是云端可访问的 http(s) URL，不能使用 localhost、内网或相对路径"
        storage_provider = str(extra.get("storage_provider") or extra.get("provider") or "").strip().lower()
        if storage_provider in {"qiniu", "kodo", "qiniu_kodo"}:
            api_key = config.get_api_key_decrypted()
            api_secret = config.get_api_secret_decrypted()
            bucket = str(extra.get("bucket") or extra.get("bucket_name") or "").strip()
            if not api_key or not api_secret or not bucket:
                return "failed", "七牛对象存储需要配置 Access Key、Secret Key 和 bucket，不能仅映射公网域名"
            upload_url = str(extra.get("upload_url") or "https://upload.qiniup.com").strip()
            if not _is_public_http_url(upload_url):
                return "failed", "七牛上传地址必须是云端可访问的 http(s) URL"
        local_prefix = extra.get("local_static_prefix") or "/static/"
        public_prefix = extra.get("public_static_prefix") or "/static/"
        if not str(local_prefix).startswith("/") or not str(public_prefix).startswith("/"):
            return "failed", "静态路径前缀必须以 / 开头"
        if storage_provider in {"qiniu", "kodo", "qiniu_kodo"}:
            return "success", f"七牛对象存储上传出口可用：{public_base_url.rstrip('/')}{str(public_prefix).rstrip('/')}/..."
        return "success", f"对象存储/CDN公网出口可用：{public_base_url.rstrip('/')}{str(public_prefix).rstrip('/')}/..."

    return "configured", "配置完整；该适配器将在任务提交时验证"


@router.get("/providers", response_model=List[ExternalAPIProviderResponse])
async def list_providers(db: AsyncSession = Depends(get_db)):
    providers = await _ensure_default_providers(db)
    return [
        ExternalAPIProviderResponse(**build_legacy_external_provider_response(provider))
        for provider in select_legacy_external_providers(providers)
    ]


@router.get("/configs", response_model=List[ExternalAPIConfigResponse])
async def list_configs(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    await _ensure_default_providers(db)
    result = await db.execute(
        select(ExternalAPIConfig, ExternalAPIProvider)
        .join(ExternalAPIProvider, ExternalAPIConfig.provider_id == ExternalAPIProvider.id)
        .where(and_(ExternalAPIConfig.user_id == user_id, ExternalAPIConfig.is_active == True))
        .order_by(desc(ExternalAPIConfig.is_default), desc(ExternalAPIConfig.created_at))
    )
    return [_config_response(config, provider) for config, provider in result.all()]


@router.post("/configs", response_model=ExternalAPIConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_config(
    request: ExternalAPIConfigCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    provider = await _get_provider(db, request.provider_id)
    if request.is_default:
        await _unset_default_for_provider(db, user_id, provider.id)

    config = ExternalAPIConfig(
        id=str(uuid4()),
        user_id=user_id,
        provider_id=provider.id,
        name=request.name,
        api_key="",
        api_secret=None,
        custom_base_url=request.custom_base_url,
        timeout=request.timeout,
        retry_count=request.retry_count,
        description=request.description,
        extra_config=request.extra_config or {},
        is_default=request.is_default,
        test_status="pending",
    )
    config.set_api_key_encrypted(request.api_key or "")
    config.set_api_secret_encrypted(request.api_secret)
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return _config_response(config, provider)


@router.put("/configs/{config_id}", response_model=ExternalAPIConfigResponse)
async def update_config(
    config_id: str,
    request: ExternalAPIConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    config, provider = await _get_config_with_provider(db, user_id, config_id)
    data = request.model_dump(exclude_unset=True)
    if data.pop("is_default", None):
        await _unset_default_for_provider(db, user_id, provider.id)
        config.is_default = True
    elif request.is_default is False:
        config.is_default = False
    if "api_key" in data:
        config.set_api_key_encrypted(data.pop("api_key") or "")
    if "api_secret" in data:
        config.set_api_secret_encrypted(data.pop("api_secret"))
    for key, value in data.items():
        setattr(config, key, value)
    config.updated_at = utc_now()
    await db.commit()
    await db.refresh(config)
    return _config_response(config, provider)


@router.post("/configs/{config_id}/test", response_model=ExternalAPITestResponse)
async def test_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    config, provider = await _get_config_with_provider(db, user_id, config_id)
    status_value, message = await _test_external_config(config, provider)
    config.test_status = status_value
    config.test_message = message
    config.tested_at = utc_now()
    await db.commit()
    return ExternalAPITestResponse(
        config_id=config.id,
        status=status_value,
        success=status_value in {"success", "configured"},
        message=message,
        checked_at=config.tested_at,
    )


@router.post("/configs/{config_id}/delivery-test", response_model=ExternalAPIDeliveryTestResponse)
async def test_config_media_delivery(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    config, provider = await _get_config_with_provider(db, user_id, config_id)
    if provider.api_type != "storage":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只有对象存储/CDN配置支持媒体交付自检")

    status_value, base_message = await _test_external_config(config, provider)
    if status_value == "failed":
        config.test_status = "failed"
        config.test_message = base_message
        config.tested_at = utc_now()
        await db.commit()
        return ExternalAPIDeliveryTestResponse(
            config_id=config.id,
            status="failed",
            success=False,
            message=base_message,
            checked_at=config.tested_at,
            source_url="",
        )

    source_url = _write_delivery_probe_file()
    delivery = await resolve_provider_media_url(
        db,
        user_id,
        source_url,
        media_type="image",
        storage_config_id=config.id,
    )
    provider_url = delivery.get("provider_url")
    if not delivery.get("image_url_sent") or not provider_url:
        message = delivery.get("omitted_reason") or "对象存储未返回云端可读 URL"
        config.test_status = "failed"
        config.test_message = message
        config.tested_at = utc_now()
        await db.commit()
        return ExternalAPIDeliveryTestResponse(
            config_id=config.id,
            status="failed",
            success=False,
            message=message,
            checked_at=config.tested_at,
            source_url=source_url,
            delivery_method=delivery.get("delivery_method"),
            object_key=delivery.get("object_key"),
            provider_url_preview=_mask_url_for_response(provider_url),
        )

    download_status: Optional[int] = None
    try:
        async with httpx.AsyncClient(timeout=min(config.timeout or 15, 15), follow_redirects=True) as client:
            response = await client.get(provider_url)
        download_status = response.status_code
        response.raise_for_status()
    except Exception as exc:
        message = f"对象存储已生成 URL，但云端读取失败：{exc}"
        config.test_status = "failed"
        config.test_message = message
        config.tested_at = utc_now()
        await db.commit()
        return ExternalAPIDeliveryTestResponse(
            config_id=config.id,
            status="failed",
            success=False,
            message=message,
            checked_at=config.tested_at,
            source_url=source_url,
            delivery_method=delivery.get("delivery_method"),
            object_key=delivery.get("object_key"),
            download_status=download_status,
            provider_url_preview=_mask_url_for_response(provider_url),
        )

    message = "真实媒体交付自检通过：本地 /static 探针文件已转换为云端可读 URL，并完成下载验证"
    config.test_status = "success"
    config.test_message = message
    config.tested_at = utc_now()
    await db.commit()
    return ExternalAPIDeliveryTestResponse(
        config_id=config.id,
        status="success",
        success=True,
        message=message,
        checked_at=config.tested_at,
        source_url=source_url,
        delivery_method=delivery.get("delivery_method"),
        object_key=delivery.get("object_key"),
        download_status=download_status,
        provider_url_preview=_mask_url_for_response(provider_url),
    )


@router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    config, _provider = await _get_config_with_provider(db, user_id, config_id)
    config.is_active = False
    config.is_default = False
    config.updated_at = utc_now()
    await db.commit()


@router.get("/capability-status", response_model=ProductionCapabilityStatus)
async def capability_status(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    providers = await list_providers(db)
    configs = await list_configs(db, user_id)
    by_type: Dict[str, Dict[str, Any]] = {}
    for provider in providers:
        by_type.setdefault(provider.api_type, {"provider_count": 0, "configured_count": 0, "ready_count": 0})
        by_type[provider.api_type]["provider_count"] += 1
    for config in configs:
        bucket = by_type.setdefault(config.api_type, {"provider_count": 0, "configured_count": 0, "ready_count": 0})
        bucket["configured_count"] += 1
        if config.test_status in {"success", "configured"}:
            bucket["ready_count"] += 1
    return ProductionCapabilityStatus(
        providers=providers,
        configs=configs,
        readiness=by_type,
        registry=get_registry(),
    )


@router.get("/qwen/models")
async def list_qwen_models():
    return QWEN_MODELS
