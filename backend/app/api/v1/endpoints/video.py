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
from app.core.model_registry import get_task_default
from app.core.security import get_current_user_id
from app.core.volcano_agent_plan_config import VOLCANO_AGENT_PLAN_PROVIDER_ID
from app.models.video_job import VideoJob
from app.services.media_persistence import persist_remote_media_url
from app.services.media_delivery import resolve_provider_media_url
from app.services.consistency_context import get_project_for_context, get_story_bible_for_context
from app.services.consistency_preflight import build_generation_context_package
from app.services.novel_continuity import build_novel_continuity_package
from app.services.prompt_composer import compose_generation_prompt
from app.services.prompt_skill_service import active_prompt_skill_entries
from app.services.asset_lock_service import AssetLockService
from app.services.story_prompt_context import build_video_continuity_constraints, load_story_prompt_context
from app.api.v1.endpoints.dashboard import log_activity

router = APIRouter(tags=["视频生成"])


# ============== 常量配置 ==============

VIDEO_MODEL_ID = "Doubao-Seedance-1.0-pro-fast"  # 已验证的快速视频模型

# 所有可选视频模型（按VOLCANO_MODELS配置）
VIDEO_MODEL_OPTIONS = [
    {"id": "Doubao-Seedance-1.0-pro-fast", "label": "豆包Seedance-1.0-pro-fast", "desc": "快速版，速度快，支持文生视频/图生视频"},
    {"id": "Doubao-Seedance-1.5-pro",        "label": "豆包Seedance-1.5-pro",        "desc": "Pro版，高质量（注：需账户有对应额度）"},
]

STATIC_ROOT = Path(__file__).resolve().parents[4] / "static"
MAX_PROVIDER_SEED = 2_147_483_647


# ============== 请求/响应模型 ==============

class VideoGenerateRequest(BaseModel):
    """视频生成请求"""
    prompt: str = Field(..., description="视频描述")
    model: str = Field(VIDEO_MODEL_ID, description="模型ID，可选 Doubao-Seedance-1.0-pro-fast / Doubao-Seedance-1.5-pro")
    duration: int = Field(5, ge=4, le=10, description="视频时长（秒），支持4/5/8/10秒")
    resolution: str = Field("720p", description="分辨率: 480p, 720p, 1080p")
    api_key: Optional[str] = Field(None, description="火山引擎API Key（可选，默认使用用户在LLM配置中的密钥）")
    model_config_id: Optional[str] = Field(None, description="已保存的视频模型配置ID")
    image_url: Optional[str] = Field(None, description="参考图片URL，用于图生视频")
    seed: Optional[int] = Field(None, description="随机种子")
    project_id: Optional[str] = Field(None, description="来源项目ID")
    workflow_id: Optional[str] = Field(None, description="来源工作流ID")
    shot_id: Optional[str] = Field(None, description="来源镜头ID")
    storyboard_id: Optional[str] = Field(None, description="来源分镜ID")
    script_id: Optional[str] = Field(None, description="来源剧本ID")
    chapter_id: Optional[str] = Field(None, description="来源章节ID")
    novel_id: Optional[str] = Field(None, description="来源小说ID")
    story_bible_id: Optional[str] = Field(None, description="用于一致性约束的 Story Bible ID")
    character_ids: List[str] = Field(default_factory=list, description="需要注入一致性设定的角色ID列表")
    use_consistency_context: bool = Field(True, description="是否自动注入 Story Bible/项目/镜头/角色一致性上下文")
    unsafe_skip_consistency_preflight: bool = Field(False, description="仅用于明确的生产降级调试：跳过一致性预检")


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


def _create_ark_client(api_key: str, base_url: Optional[str] = None):
    """创建ARK客户端"""
    from volcenginesdkarkruntime import Ark
    return Ark(
        base_url=base_url or "https://ark.cn-beijing.volces.com/api/v3",
        api_key=api_key,
    )


def _get_volcano_model_name(model_id: str) -> str:
    """根据模型ID获取模型名称"""
    from app.core.volcano_config import VOLCANO_MODELS
    for m in VOLCANO_MODELS:
        if m["id"] == model_id:
            return m.get("name_cn", m.get("name", model_id))
    # 未知模型，返回ID本身
    return model_id


async def _resolve_video_model_config(
    db: AsyncSession,
    user_id: str,
    requested_model: Optional[str],
    config_id: Optional[str] = None,
) -> dict[str, Any]:
    """Resolve the selected video model to provider/API model/config."""
    from app.core.volcano_config import get_endpoint_id
    from app.models import LLMConfig, LLMModel, LLMProvider

    if config_id:
        config_result = await db.execute(
            select(LLMConfig, LLMModel, LLMProvider)
            .join(LLMModel, LLMConfig.model_id == LLMModel.id)
            .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
            .where(
                and_(
                    LLMConfig.id == config_id,
                    LLMConfig.user_id == user_id,
                    LLMConfig.is_active == True,
                    LLMModel.is_active == True,
                    LLMProvider.is_active == True,
                )
            )
            .limit(1)
        )
        config_row = config_result.first()
        if not config_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="所选视频模型配置不存在或已停用")
        config, model, provider = config_row
        model_type = (model.model_type or "").lower()
        capabilities = [str(item).lower() for item in (model.capabilities or [])]
        if model_type not in {"video", "video-generation", "video_generation"} and not any("video" in item for item in capabilities):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"所选模型不是视频生成模型：{model.model_name}")
        provider_id = provider.name or provider.id
        config_extra = config.extra_params or {}
        endpoint_id = get_endpoint_id(model.model_id) if provider_id == "volcano" else model.model_id
        return {
            "provider_id": provider_id,
            "provider_name": provider.name_cn or provider.name,
            "api_model_id": model.model_id,
            "config_model_id": model.id,
            "model_config_id": config.id,
            "model_name": model.model_name_cn or model.model_name,
            "model_type": model_type,
            "base_url": config_extra.get("base_url") or model.base_url or provider.base_url,
            "api_key": config.get_api_key_decrypted(),
            "test_status": config.test_status,
            "model_endpoint_id": endpoint_id,
            "capabilities": model.capabilities or [],
        }

    model_key = requested_model or VIDEO_MODEL_ID
    row = None
    if model_key:
        result = await db.execute(
            select(LLMModel, LLMProvider)
            .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
            .where(
                and_(
                    LLMModel.is_active == True,
                    LLMProvider.is_active == True,
                    or_(LLMModel.id == model_key, LLMModel.model_id == model_key),
                )
            )
            .limit(1)
        )
        row = result.first()

    if row:
        model, provider = row
        model_type = model.model_type or ""
        if model_type not in {"video", "video-generation"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"所选模型不是视频生成模型：{model.model_name}",
            )
        config_result = await db.execute(
            select(LLMConfig)
            .where(
                and_(
                    LLMConfig.user_id == user_id,
                    LLMConfig.model_id == model.id,
                    LLMConfig.is_active == True,
                )
            )
            .order_by(desc(LLMConfig.is_default), desc(LLMConfig.updated_at), desc(LLMConfig.created_at))
            .limit(1)
        )
        config = config_result.scalar_one_or_none()
        provider_id = provider.name or provider.id
        config_extra = config.extra_params or {} if config else {}
        endpoint_id = get_endpoint_id(model.model_id) if provider_id == "volcano" else model.model_id
        return {
            "provider_id": provider_id,
            "provider_name": provider.name_cn or provider.name,
            "api_model_id": model.model_id,
            "config_model_id": model.id,
            "model_config_id": config.id if config else None,
            "model_name": model.model_name_cn or model.model_name,
            "model_type": model_type,
            "base_url": config_extra.get("base_url") or model.base_url or provider.base_url,
            "api_key": config.get_api_key_decrypted() if config else None,
            "test_status": config.test_status if config else None,
            "model_endpoint_id": endpoint_id,
            "capabilities": model.capabilities or [],
        }

    return {
        "provider_id": "volcano",
        "provider_name": "火山引擎",
        "api_model_id": model_key,
        "config_model_id": None,
        "model_name": _get_volcano_model_name(model_key),
        "model_type": "video-generation",
        "base_url": None,
        "api_key": None,
        "test_status": None,
        "model_endpoint_id": get_endpoint_id(model_key),
        "capabilities": ["text-to-video", "image-to-video"],
    }


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


async def _resolve_provider_image_delivery(db: AsyncSession, user_id: str, image_url: Optional[str]) -> dict[str, Any]:
    delivery = await resolve_provider_media_url(db, user_id, image_url, media_type="图")
    return {
        "provider_image_url": delivery.get("provider_url"),
        "image_url_omitted_reason": delivery.get("omitted_reason"),
        "image_delivery": delivery,
    }


def _provider_image_url_error_message(exc: Exception, provider_image_url: Optional[str]) -> Optional[str]:
    error_text = str(exc)
    if "image_url" not in error_text:
        return None
    if "InvalidParameter" not in error_text and "not valid" not in error_text and "BadRequest" not in error_text:
        return None
    if provider_image_url:
        return (
            "参考图地址已提交给云端视频模型，但模型拒绝了该图片 URL。请确认图片是可公网访问、未过期的 http(s) 地址，"
            f"或改用无参考图模式后重试。原始错误：{error_text}"
        )
    return (
        "参考图不是可公网访问的 URL，已不应传给云端视频模型；请重新生成/上传公网可访问参考图，"
        f"或使用无参考图模式后重试。原始错误：{error_text}"
    )


def _append_provider_image_note(prompt: str, omission_reason: Optional[str]) -> str:
    if not omission_reason:
        return prompt
    return (
        f"{prompt}\n\n参考图接入说明：{omission_reason}，本次云端调用不传 image_url；"
        "请依据上文角色视觉DNA、场景、道具、风格锁和剧情连续性生成，保持人物形象与分镜逻辑一致。"
    )


def _video_prompt_parameters(
    request: VideoGenerateRequest,
    seed: Optional[int],
    provider_image_url: Optional[str] = None,
    image_url_omitted_reason: Optional[str] = None,
    image_delivery: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    parameters = {
        "duration": request.duration,
        "resolution": request.resolution,
        "camera_fixed": False,
        "watermark": True,
        "seed": seed,
        "image_url": request.image_url,
        "provider_image_url": provider_image_url,
        "image_url_sent": bool(provider_image_url),
        "model_config_id": request.model_config_id,
    }
    if request.image_url and image_url_omitted_reason:
        parameters["image_url_omitted_reason"] = image_url_omitted_reason
    if image_delivery:
        parameters["image_delivery_method"] = image_delivery.get("delivery_method")
        parameters["image_delivery_config_id"] = image_delivery.get("storage_config_id")
        parameters["image_delivery_provider"] = image_delivery.get("storage_provider_name")
    return parameters


def _video_model_metadata(video_model_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider_id": video_model_config.get("provider_id"),
        "provider_name": video_model_config.get("provider_name"),
        "model_config_id": video_model_config.get("model_config_id"),
        "config_model_id": video_model_config.get("config_model_id"),
        "api_model_id": video_model_config.get("api_model_id"),
        "model_endpoint_id": video_model_config.get("model_endpoint_id"),
        "model_type": video_model_config.get("model_type"),
        "model_test_status": video_model_config.get("test_status"),
        "model_capabilities": video_model_config.get("capabilities") or [],
    }


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


async def _sync_video_job_and_shot(
    db: AsyncSession,
    job: VideoJob,
    status_value: str,
    progress: Optional[int],
    video_url: Optional[str],
    cover_url: Optional[str],
    error_message: Optional[str] = None,
):
    """Persist provider status and mirror shot output when a job is shot-linked."""
    original_video_url = video_url
    original_cover_url = cover_url
    extra_data = job.extra_data if isinstance(job.extra_data, dict) else {}
    if status_value == "succeeded" and video_url:
        try:
            video_url = await persist_remote_media_url(
                video_url,
                media_type="video",
                subdir="videos",
                prefix=f"video-{job.id[:8]}",
                max_bytes=300 * 1024 * 1024,
            ) or video_url
            if video_url != original_video_url:
                extra_data["original_video_url"] = original_video_url
                extra_data["video_persisted"] = True
        except Exception as exc:
            extra_data["video_persisted"] = False
            extra_data["video_persist_error"] = str(exc)
    if status_value == "succeeded" and cover_url:
        try:
            cover_url = await persist_remote_media_url(
                cover_url,
                media_type="image",
                subdir="images",
                prefix=f"video-cover-{job.id[:8]}",
                max_bytes=20 * 1024 * 1024,
            ) or cover_url
            if cover_url != original_cover_url:
                extra_data["original_cover_url"] = original_cover_url
        except Exception as exc:
            extra_data["cover_persist_error"] = str(exc)

    job.status = status_value
    if progress is not None:
        job.progress = progress
    if video_url:
        job.video_url = video_url
    if cover_url:
        job.cover_url = cover_url
    if error_message:
        job.error_message = error_message
    job.extra_data = extra_data

    shot_id = extra_data.get("shot_id")
    if shot_id:
        from app.models import Shot

        shot_result = await db.execute(
            select(Shot).where(Shot.id == shot_id, Shot.user_id == job.user_id)
        )
        shot = shot_result.scalar_one_or_none()
        if shot:
            shot.video_status = status_value
            if video_url:
                shot.video_url = video_url


def _json_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _ensure_match(current: Optional[str], incoming: Optional[str], detail: str) -> Optional[str]:
    if current and incoming and current != incoming:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)
    return current or incoming


async def _resolve_video_lineage(db: AsyncSession, user_id: str, request: VideoGenerateRequest) -> dict:
    """Infer and validate the full novel/chapter/script/storyboard/shot lineage."""
    from app.models import Chapter, Novel, Script, Shot, Storyboard, Workflow

    lineage = {
        "project_id": request.project_id,
        "workflow_id": request.workflow_id,
        "novel_id": request.novel_id,
        "chapter_id": request.chapter_id,
        "script_id": request.script_id,
        "storyboard_id": request.storyboard_id,
        "shot_id": request.shot_id,
    }

    workflow = None
    if request.workflow_id:
        workflow_result = await db.execute(
            select(Workflow).where(Workflow.id == request.workflow_id, Workflow.user_id == user_id)
        )
        workflow = workflow_result.scalar_one_or_none()
        if workflow is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")
        lineage["novel_id"] = _ensure_match(lineage["novel_id"], workflow.novel_id, "workflow_id 与 novel_id 不匹配")
        lineage["chapter_id"] = _ensure_match(lineage["chapter_id"], workflow.chapter_id, "workflow_id 与 chapter_id 不匹配")
        lineage["script_id"] = _ensure_match(lineage["script_id"], workflow.script_id, "workflow_id 与 script_id 不匹配")
        lineage["storyboard_id"] = _ensure_match(lineage["storyboard_id"], workflow.storyboard_id, "workflow_id 与 storyboard_id 不匹配")

    shot = None
    storyboard = None
    script = None
    chapter = None
    novel = None

    if lineage["shot_id"]:
        shot_result = await db.execute(
            select(Shot).where(Shot.id == lineage["shot_id"], Shot.user_id == user_id)
        )
        shot = shot_result.scalar_one_or_none()
        if shot is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="镜头不存在")
        lineage["storyboard_id"] = _ensure_match(lineage["storyboard_id"], shot.storyboard_id, "shot_id 与 storyboard_id 不匹配")

    if lineage["storyboard_id"]:
        storyboard_result = await db.execute(
            select(Storyboard).where(Storyboard.id == lineage["storyboard_id"], Storyboard.user_id == user_id)
        )
        storyboard = storyboard_result.scalar_one_or_none()
        if storyboard is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分镜不存在")
        lineage["script_id"] = _ensure_match(lineage["script_id"], storyboard.script_id, "storyboard_id 与 script_id 不匹配")
        lineage["novel_id"] = _ensure_match(lineage["novel_id"], storyboard.novel_id, "storyboard_id 与 novel_id 不匹配")
        storyboard_content = _json_dict(storyboard.content)
        lineage["chapter_id"] = _ensure_match(
            lineage["chapter_id"],
            storyboard_content.get("chapter_id"),
            "storyboard_id 与 chapter_id 不匹配",
        )

    if lineage["script_id"]:
        script_result = await db.execute(
            select(Script).where(Script.id == lineage["script_id"], Script.user_id == user_id)
        )
        script = script_result.scalar_one_or_none()
        if script is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="剧本不存在")
        lineage["novel_id"] = _ensure_match(lineage["novel_id"], script.novel_id, "script_id 与 novel_id 不匹配")
        script_extra = _json_dict(script.extra_data)
        lineage["chapter_id"] = _ensure_match(
            lineage["chapter_id"],
            script_extra.get("chapter_id"),
            "script_id 与 chapter_id 不匹配",
        )

    if lineage["chapter_id"]:
        chapter_result = await db.execute(
            select(Chapter).where(Chapter.id == lineage["chapter_id"], Chapter.user_id == user_id)
        )
        chapter = chapter_result.scalar_one_or_none()
        if chapter is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在")
        lineage["novel_id"] = _ensure_match(lineage["novel_id"], chapter.novel_id, "chapter_id 与 novel_id 不匹配")

    if lineage["novel_id"]:
        novel_result = await db.execute(
            select(Novel).where(Novel.id == lineage["novel_id"], Novel.user_id == user_id)
        )
        novel = novel_result.scalar_one_or_none()
        if novel is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="小说不存在")

    if workflow:
        workflow.novel_id = lineage["novel_id"] or workflow.novel_id
        workflow.chapter_id = lineage["chapter_id"] or workflow.chapter_id
        workflow.script_id = lineage["script_id"] or workflow.script_id
        workflow.storyboard_id = lineage["storyboard_id"] or workflow.storyboard_id

    return {
        **lineage,
        "novel_title": novel.title if novel else None,
        "chapter_title": chapter.title if chapter else None,
        "chapter_number": chapter.chapter_number if chapter else None,
        "script_title": script.title if script else None,
        "storyboard_title": storyboard.title if storyboard else None,
        "shot_number": shot.shot_number if shot else None,
        "shot": shot,
        "storyboard": storyboard,
        "script": script,
    }


def _extract_shot_generation_context(shot) -> dict:
    if not shot:
        return {
            "character_refs": [],
            "scene_refs": [],
            "prop_refs": [],
            "event_refs": [],
            "environment_context": None,
            "subtitle_text": None,
        }
    extra = _json_dict(getattr(shot, "extra_data", None))
    entity_refs = _json_dict(extra.get("entity_refs"))
    character_refs = getattr(shot, "character_refs", None) or entity_refs.get("characters") or []
    return {
        "character_refs": character_refs,
        "scene_refs": extra.get("scene_refs") or entity_refs.get("scenes") or [],
        "prop_refs": extra.get("prop_refs") or entity_refs.get("props") or [],
        "event_refs": extra.get("event_refs") or entity_refs.get("events") or [],
        "environment_context": extra.get("environment_context"),
        "subtitle_text": extra.get("subtitle_text") or getattr(shot, "dialogue", None),
    }


def _json_list(value) -> list:
    return value if isinstance(value, list) else []


def _ref_name(ref: Any) -> str:
    if isinstance(ref, dict):
        return str(ref.get("name") or ref.get("entity_name") or "").strip()
    return str(ref or "").strip()


def _compact_ref_key(ref: dict) -> str:
    return str(ref.get("character_id") or ref.get("entity_id") or ref.get("name") or "").strip()


def _dedupe_refs(refs: List[dict]) -> List[dict]:
    result: List[dict] = []
    seen: set[str] = set()
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        key = _compact_ref_key(ref)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(ref)
    return result


def _merge_character_ref(character, *, source: str, ref: Optional[dict] = None) -> dict:
    merged = dict(ref or {})
    merged.update(
        {
            "character_id": character.id,
            "name": character.name,
            "description": character.description,
            "appearance": character.appearance,
            "personality": character.personality,
            "voice": character.voice,
            "avatar": character.avatar,
            "source": source,
        }
    )
    return merged


def _character_scope_rank(character, novel_id: Optional[str], chapter_id: Optional[str]) -> int:
    if chapter_id and getattr(character, "chapter_id", None) == chapter_id:
        return 4
    if novel_id and getattr(character, "novel_id", None) == novel_id:
        return 3
    if getattr(character, "novel_id", None) is None:
        return 1
    return 0


def _character_matches_name(character, name: str) -> bool:
    if not name:
        return False
    names = [getattr(character, "name", None)]
    tags = getattr(character, "tags", None)
    if isinstance(tags, list):
        names.extend(str(item) for item in tags)
    return any(item and str(item).strip() == name for item in names)


def _lookup_character_by_name(characters: List[Any], name: str, novel_id: Optional[str], chapter_id: Optional[str]):
    matches = [character for character in characters if _character_matches_name(character, name)]
    if not matches:
        return None
    return sorted(
        matches,
        key=lambda item: (_character_scope_rank(item, novel_id, chapter_id), str(getattr(item, "updated_at", "") or "")),
        reverse=True,
    )[0]


def _name_contains_character(name: str, character_names: set[str]) -> bool:
    return any(character_name and character_name in name for character_name in character_names)


def _is_valid_story_entity_character_ref(ref: dict) -> bool:
    name = _ref_name(ref)
    if not name:
        return False
    if name in {"疼痛", "狂喜", "活着", "阳光", "年轻", "瘦弱", "身躯", "眼睛", "双手", "起身", "个人"}:
        return False
    evidence = str(ref.get("evidence") or "")
    description = str(ref.get("description") or "")
    if "规则识别人物" in description or "规则识别人物" in evidence:
        return False
    return bool(ref.get("entity_id") or "文本标注角色" in description or "角色" in evidence)


def _format_visual_locks(character_refs: List[dict]) -> str:
    lines = []
    for ref in character_refs[:6]:
        name = ref.get("name")
        details = []
        for key, label in (("appearance", "外貌"), ("description", "身份"), ("personality", "性格")):
            value = ref.get(key)
            if value:
                details.append(f"{label}:{value}")
        if name:
            lines.append(f"{name}（{'；'.join(details) if details else '使用角色设定'}）")
    return "；".join(lines)


def _format_asset_locks(locks: List[dict], *, limit: int = 8) -> str:
    parts = []
    for lock in locks[:limit]:
        name = lock.get("entity_name") or lock.get("name")
        category = lock.get("category")
        url = lock.get("url") or lock.get("thumbnail_url")
        if name and url:
            parts.append(f"{name}({category or 'reference'}): {url}")
        elif name:
            parts.append(str(name))
    return "；".join(parts)


def _collect_character_multiview_refs(
    assets: List[Any],
    character_refs: List[dict],
    *,
    per_character: int = 8,
) -> List[dict]:
    """Normalize locked character multi-view image assets for video prompts."""
    character_names = {
        str(ref.get("character_id")): str(ref.get("name") or "")
        for ref in character_refs
        if isinstance(ref, dict) and ref.get("character_id")
    }
    entity_to_character_id = {
        str(ref.get("entity_id")): str(ref.get("character_id"))
        for ref in character_refs
        if isinstance(ref, dict) and ref.get("entity_id") and ref.get("character_id")
    }
    if not character_names:
        return []

    angle_order = {
        "front": 0,
        "three_quarter": 1,
        "3/4": 1,
        "side": 2,
        "back": 3,
        "closeup": 4,
        "expression": 5,
        "costume": 6,
    }
    candidates: List[tuple[int, int, int, dict]] = []
    seen: set[tuple[str, str, str]] = set()
    counts: dict[str, int] = {}
    for asset in assets:
        character_id = str(getattr(asset, "character_id", "") or "")
        if not character_id:
            entity_id = str(getattr(asset, "entity_id", "") or "")
            character_id = entity_to_character_id.get(entity_id, "")
        if character_id not in character_names:
            continue
        if getattr(asset, "category", None) != "character":
            continue
        url = getattr(asset, "url", None) or getattr(asset, "thumbnail_url", None)
        if not url:
            continue
        params = getattr(asset, "generation_params", None)
        params = params if isinstance(params, dict) else {}
        reference_role = str(params.get("reference_role") or params.get("role") or "").strip()
        view_angle = str(params.get("view_angle") or params.get("angle") or "reference").strip()
        if reference_role not in {"character_multiview", "multi_view", "multiview"} and "view" not in reference_role and not params.get("view_angle"):
            continue
        if not (getattr(asset, "is_locked", False) or getattr(asset, "is_final", False)):
            continue
        key = (character_id, view_angle, url)
        if key in seen:
            continue
        seen.add(key)
        counts[character_id] = counts.get(character_id, 0) + 1
        if counts[character_id] > per_character:
            continue
        ref = {
            "asset_id": getattr(asset, "id", None),
            "character_id": character_id,
            "character_name": character_names.get(character_id),
            "name": getattr(asset, "name", None),
            "view_angle": view_angle,
            "url": url,
            "thumbnail_url": getattr(asset, "thumbnail_url", None),
            "version": getattr(asset, "version", None),
            "is_locked": bool(getattr(asset, "is_locked", False)),
            "is_final": bool(getattr(asset, "is_final", False)),
            "reference_role": reference_role or "character_multiview",
        }
        character_rank = list(character_names.keys()).index(character_id)
        candidates.append(
            (
                character_rank,
                angle_order.get(view_angle, 99),
                -int(getattr(asset, "version", None) or 0),
                ref,
            )
        )
    candidates.sort(key=lambda item: item[:3])
    return [item[3] for item in candidates]


def _format_multiview_refs(refs: List[dict], *, limit: int = 12) -> str:
    parts = []
    for ref in refs[:limit]:
        name = ref.get("character_name") or ref.get("name")
        angle = ref.get("view_angle")
        url = ref.get("url")
        if name and angle and url:
            parts.append(f"{name}-{angle}: {url}")
        elif name and url:
            parts.append(f"{name}: {url}")
    return "；".join(parts)


async def _load_video_scope_characters(db: AsyncSession, user_id: str, *, novel_id: Optional[str], chapter_id: Optional[str]) -> List[Any]:
    from app.models import Character

    filters = [Character.user_id == user_id]
    if novel_id:
        filters.append(or_(Character.novel_id == novel_id, Character.novel_id.is_(None)))
    elif chapter_id:
        filters.append(or_(Character.chapter_id == chapter_id, Character.novel_id.is_(None)))
    result = await db.execute(select(Character).where(and_(*filters)).order_by(desc(Character.updated_at)))
    return list(result.scalars().all())


async def _build_video_consistency_package(
    db: AsyncSession,
    user_id: str,
    request: VideoGenerateRequest,
    lineage: dict,
) -> dict:
    """Build the effective video prompt package used by single and batch generation."""
    shot = lineage.get("shot")
    shot_context = _extract_shot_generation_context(shot)
    novel_id = request.novel_id or lineage.get("novel_id")
    chapter_id = request.chapter_id or lineage.get("chapter_id")
    characters = await _load_video_scope_characters(db, user_id, novel_id=novel_id, chapter_id=chapter_id)
    character_by_id = {character.id: character for character in characters}
    if request.character_ids:
        missing_requested = [item for item in request.character_ids if item not in character_by_id]
        if missing_requested:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="所选角色不存在或不属于当前小说，请重新选择当前小说下的角色参考",
            )
    valid_character_refs: List[dict] = []
    filtered_out_refs: List[dict] = []

    for ref in _json_list(shot_context.get("character_refs")):
        if not isinstance(ref, dict):
            continue
        character = None
        character_id = ref.get("character_id") or ref.get("id")
        if character_id:
            character = character_by_id.get(character_id)
        if character is None:
            character = _lookup_character_by_name(
                characters,
                _ref_name(ref),
                novel_id,
                chapter_id,
            )
        if character is None:
            if _is_valid_story_entity_character_ref(ref):
                valid_character_refs.append(dict(ref))
            else:
                filtered_out_refs.append(ref)
            continue
        else:
            valid_character_refs.append(_merge_character_ref(character, source=ref.get("source") or "shot_ref", ref=ref))

    explicit_characters = [character_by_id[item] for item in request.character_ids if item in character_by_id]
    for character in explicit_characters:
        valid_character_refs.append(_merge_character_ref(character, source="request_character"))

    shot_text = " ".join(
        str(value or "")
        for value in [
            getattr(shot, "prompt", None),
            getattr(shot, "visual_description", None),
            getattr(shot, "dialogue", None),
            shot_context.get("subtitle_text"),
        ]
    )
    matched_from_text = [
        character
        for character in characters
        if character.novel_id == novel_id and character.name and character.name in shot_text
    ]
    if not valid_character_refs:
        matched_from_text = matched_from_text or [character for character in characters if character.novel_id == novel_id]
        for character in matched_from_text[:3]:
            valid_character_refs.append(_merge_character_ref(character, source="novel_character_fallback"))
    else:
        for character in matched_from_text[:3]:
            valid_character_refs.append(_merge_character_ref(character, source="shot_text_match"))

    valid_character_refs = _dedupe_refs(valid_character_refs)
    valid_character_names = {str(ref.get("name")) for ref in valid_character_refs if ref.get("name")}

    scene_refs = _dedupe_refs([ref for ref in _json_list(shot_context.get("scene_refs")) if isinstance(ref, dict)])
    event_refs = _dedupe_refs([ref for ref in _json_list(shot_context.get("event_refs")) if isinstance(ref, dict)])
    prop_refs = []
    filtered_out_prop_refs = []
    for ref in _json_list(shot_context.get("prop_refs")):
        if not isinstance(ref, dict):
            continue
        name = _ref_name(ref)
        if _name_contains_character(name, valid_character_names):
            filtered_out_prop_refs.append(ref)
            continue
        prop_refs.append(ref)
    prop_refs = _dedupe_refs(prop_refs)

    production_context = _json_dict(_json_dict(getattr(shot, "extra_data", None)).get("production_context")) if shot else {}
    asset_locks = [item for item in _json_list(production_context.get("asset_version_locks")) if isinstance(item, dict)]
    character_multiview_refs = [
        item for item in _json_list(production_context.get("character_multiview_refs")) if isinstance(item, dict)
    ]
    if not character_multiview_refs and valid_character_refs:
        from app.models import Asset

        character_ids = [ref.get("character_id") for ref in valid_character_refs if ref.get("character_id")]
        entity_ids = [ref.get("entity_id") for ref in valid_character_refs if ref.get("entity_id")]
        asset_link_filters = []
        if character_ids:
            asset_link_filters.append(Asset.character_id.in_(character_ids))
        if entity_ids:
            asset_link_filters.append(Asset.entity_id.in_(entity_ids))
        if asset_link_filters:
            multiview_result = await db.execute(
                select(Asset)
                .where(
                    and_(
                        Asset.is_active == True,
                        or_(Asset.user_id == user_id, Asset.is_public == True),
                        Asset.category == "character",
                        or_(*asset_link_filters),
                        or_(Asset.is_locked == True, Asset.is_final == True),
                    )
                )
                .order_by(desc(Asset.is_final), desc(Asset.is_locked), desc(Asset.version), desc(Asset.updated_at))
                .limit(200)
            )
            character_multiview_refs = _collect_character_multiview_refs(
                list(multiview_result.scalars().all()),
                valid_character_refs,
            )

    reference_image = request.image_url
    reference_image_source = "request" if request.image_url else None
    if not reference_image and getattr(shot, "image_url", None):
        reference_image = shot.image_url
        reference_image_source = "shot_image"
    if not reference_image:
        for lock in asset_locks:
            if lock.get("category") == "character" and (lock.get("url") or lock.get("thumbnail_url")):
                reference_image = lock.get("url") or lock.get("thumbnail_url")
                reference_image_source = "asset_lock_character"
                break
    if not reference_image:
        for ref in character_multiview_refs:
            if ref.get("url"):
                reference_image = ref["url"]
                reference_image_source = "character_multiview"
                break
    if not reference_image:
        for ref in valid_character_refs:
            if ref.get("avatar"):
                reference_image = ref["avatar"]
                reference_image_source = "character_avatar"
                break
    if not reference_image:
        for lock in asset_locks:
            if lock.get("url") or lock.get("thumbnail_url"):
                reference_image = lock.get("url") or lock.get("thumbnail_url")
                reference_image_source = "asset_lock"
                break
    if not reference_image and (valid_character_refs or scene_refs or prop_refs):
        from app.models import Asset

        asset_names = {
            _ref_name(ref)
            for ref in [*valid_character_refs, *scene_refs, *prop_refs]
            if _ref_name(ref)
        }
        character_ids = {ref.get("character_id") for ref in valid_character_refs if ref.get("character_id")}
        asset_filters = [
            Asset.is_active == True,
            or_(Asset.user_id == user_id, Asset.is_public == True),
            Asset.category.in_(["character", "scene", "prop", "costume"]),
        ]
        if novel_id:
            asset_filters.append(or_(Asset.novel_id == novel_id, Asset.novel_id.is_(None)))
        asset_result = await db.execute(
            select(Asset)
            .where(and_(*asset_filters))
            .order_by(desc(Asset.usage_count), desc(Asset.updated_at))
            .limit(120)
        )
        for asset in asset_result.scalars().all():
            asset_text = f"{asset.name or ''} {asset.description or ''} {' '.join(asset.tags or [])}"
            if (
                (asset.character_id and asset.character_id in character_ids)
                or any(name and name in asset_text for name in asset_names)
            ) and (asset.url or asset.thumbnail_url):
                reference_image = asset.url or asset.thumbnail_url
                reference_image_source = f"asset_{asset.category}"
                break

    story_prompt_context = await load_story_prompt_context(
        db,
        user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
    )
    project = await get_project_for_context(db, user_id, request.project_id or lineage.get("project_id"), strict=False)
    story_bible = await get_story_bible_for_context(
        db,
        user_id,
        story_bible_id=request.story_bible_id,
        project_id=request.project_id or lineage.get("project_id"),
        novel_id=novel_id,
    )
    novel_continuity = await build_novel_continuity_package(
        db,
        user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        story_bible_id=story_bible.id if story_bible else request.story_bible_id,
        project_id=project.id if project else (request.project_id or lineage.get("project_id")),
        model_id=request.model,
        task="shot_video",
    )

    storyboard = lineage.get("storyboard")
    script = lineage.get("script")
    task_default = get_task_default("shot_video")
    novel_series_seed = novel_continuity.get("novel_series_seed") or _derive_stable_seed([
        "novel_series",
        project.id if project else (request.project_id or lineage.get("project_id")),
        story_bible.id if story_bible else request.story_bible_id,
        novel_id,
    ])
    chapter_seed = novel_continuity.get("chapter_seed") or _derive_stable_seed([
        "chapter",
        novel_series_seed,
        chapter_id,
    ])
    storyboard_seed = _derive_stable_seed([
        "storyboard",
        chapter_seed,
        request.script_id or lineage.get("script_id"),
        request.storyboard_id or lineage.get("storyboard_id"),
        request.model,
    ])
    shot_seed = request.seed if request.seed is not None else _derive_stable_seed([
        "shot",
        storyboard_seed,
        getattr(shot, "shot_number", None),
        request.shot_id or lineage.get("shot_id"),
        request.model,
    ])
    style_lock = {
        "scope": "novel_series",
        "series_seed": novel_series_seed,
        "novel_series_seed": novel_series_seed,
        "chapter_seed": chapter_seed,
        "storyboard_seed": storyboard_seed,
        "style": (
            getattr(story_bible, "style", None)
            or story_prompt_context.get("style")
            or getattr(storyboard, "style", None)
            or getattr(script, "style", None)
            or "统一动漫赛璐璐风格"
        ),
        "genre": story_prompt_context.get("genre") or getattr(storyboard, "genre", None) or getattr(script, "genre", None),
        "story_bible_id": story_bible.id if story_bible else request.story_bible_id,
        "storyboard_id": request.storyboard_id or lineage.get("storyboard_id"),
        "chapter_id": chapter_id,
        "novel_id": novel_id,
        "constraint": "整部小说共享同一画风、角色视觉DNA、世界观、场景/道具状态机和事件因果；章节和分镜只派生局部节奏，不重置角色形象。",
    }

    extra_context = {
        "视频时长": request.duration,
        "分辨率": request.resolution,
        "整部小说连续性锁": novel_continuity.get("prompt_block"),
        "小说级系列种子": novel_series_seed,
        "章节连续性种子": chapter_seed,
        "分镜派生种子": storyboard_seed,
        "参考图": reference_image,
        "参考图来源": reference_image_source,
        "人物角色": _ref_names(valid_character_refs),
        "角色视觉DNA锁": _format_visual_locks(valid_character_refs),
        "场景": _ref_names(scene_refs),
        "道具": _ref_names(prop_refs),
        "事件": _ref_names(event_refs),
        "环境连续性": shot_context["environment_context"],
        "字幕/对白": shot_context["subtitle_text"],
        "小说级风格锁": style_lock["constraint"],
        "资产版本锁": _format_asset_locks(asset_locks),
        "角色多视图参考": _format_multiview_refs(character_multiview_refs),
        "动漫连续性硬约束": build_video_continuity_constraints(story_prompt_context),
    }
    if storyboard:
        extra_context.setdefault("分镜标题", storyboard.title)
        if getattr(storyboard, "style", None):
            extra_context.setdefault("分镜风格", storyboard.style)
        if getattr(storyboard, "genre", None):
            extra_context.setdefault("分镜题材", storyboard.genre)
        if getattr(storyboard, "description", None):
            extra_context.setdefault("分镜说明", storyboard.description)
    if script:
        extra_context.setdefault("剧本标题", script.title)
        if getattr(script, "style", None):
            extra_context.setdefault("剧本风格", script.style)
        if getattr(script, "genre", None):
            extra_context.setdefault("剧本题材", script.genre)
        if getattr(script, "description", None):
            extra_context.setdefault("剧本说明", script.description)

    # 构建锁定资产列表用于prompt注入
    locked_assets_prompts = [
        {
            "type": lock.get("category") or "资产",
            "name": lock.get("entity_name") or lock.get("name") or "Unknown",
        }
        for lock in asset_locks
    ]
    prompt_skill_context = {"用户提示词": request.prompt, **extra_context}
    prompt_skill_entries = await active_prompt_skill_entries(
        db,
        user_id,
        task="shot_video",
        context=prompt_skill_context,
    )

    final_prompt = compose_generation_prompt(
        task="shot_video",
        shot=shot,
        story_bible=story_bible,
        characters=[
            character_by_id[ref["character_id"]]
            for ref in valid_character_refs
            if ref.get("character_id") in character_by_id
        ],
        project=project,
        extra_context=prompt_skill_context,
        locked_assets=locked_assets_prompts,
        skill_blocks=[entry["content"] for entry in prompt_skill_entries],
    )
    metadata = {
        "task": "shot_video",
        "story_bible_id": story_bible.id if story_bible else request.story_bible_id,
        "project_id": project.id if project else (request.project_id or lineage.get("project_id")),
        "novel_id": novel_id,
        "chapter_id": chapter_id,
        "shot_id": request.shot_id or lineage.get("shot_id"),
        "storyboard_id": request.storyboard_id or lineage.get("storyboard_id"),
        "character_ids": [ref["character_id"] for ref in valid_character_refs if ref.get("character_id")],
        "entity_refs": {
            "characters": valid_character_refs,
            "scenes": scene_refs,
            "props": prop_refs,
            "events": event_refs,
        },
        "subtitle_text": shot_context["subtitle_text"],
        "default_model_id": task_default.get("default_model_id") if task_default else None,
        "series_seed": novel_series_seed,
        "novel_series_seed": novel_series_seed,
        "chapter_seed": chapter_seed,
        "storyboard_seed": storyboard_seed,
        "style_lock": style_lock,
        "prompt_skill_count": len(prompt_skill_entries),
        "prompt_skills": [
            {key: entry[key] for key in ("id", "name", "task", "stage", "version")}
            for entry in prompt_skill_entries
        ],
        "continuity_lock": novel_continuity.get("continuity_lock"),
        "previous_chapter_context": novel_continuity.get("previous_chapter_context"),
        "current_chapter_context": novel_continuity.get("current_chapter_context"),
        "next_chapter_constraint": novel_continuity.get("next_chapter_constraint"),
        "previous_chapter_state": novel_continuity.get("previous_chapter_state"),
        "chapter_state_snapshot": novel_continuity.get("chapter_state_snapshot"),
        "state_machine_version": novel_continuity.get("state_machine_version"),
        "state_machine_summary": novel_continuity.get("state_machine_summary"),
        "event_timeline_tail": novel_continuity.get("event_timeline_tail") or [],
        "entity_locks": novel_continuity.get("entity_locks") or {},
        "character_visual_locks": valid_character_refs,
        "character_multiview_refs": character_multiview_refs,
        "reference_image_source": reference_image_source,
        "invalid_entity_ref_count": len(filtered_out_refs) + len(filtered_out_prop_refs),
        "seed": shot_seed,
    }
    return {
        "final_prompt": final_prompt,
        "metadata": metadata,
        "context": {
            "character_refs": valid_character_refs,
            "scene_refs": scene_refs,
            "prop_refs": prop_refs,
            "event_refs": event_refs,
            "environment_context": shot_context["environment_context"],
            "subtitle_text": shot_context["subtitle_text"],
            "asset_version_locks": asset_locks,
            "character_multiview_refs": character_multiview_refs,
            "style_lock": style_lock,
            "series_seed": novel_series_seed,
            "novel_series_seed": novel_series_seed,
            "chapter_seed": chapter_seed,
            "storyboard_seed": storyboard_seed,
            "novel_continuity": novel_continuity,
            "reference_image": reference_image,
            "reference_image_source": reference_image_source,
            "filtered_out_entity_refs": filtered_out_refs + filtered_out_prop_refs,
        },
        "seed": shot_seed,
        "series_seed": novel_series_seed,
        "novel_series_seed": novel_series_seed,
        "chapter_seed": chapter_seed,
        "reference_image": reference_image,
        "reference_image_source": reference_image_source,
    }


def _ref_names(refs: List[dict]) -> str:
    return "、".join(str(ref.get("name")) for ref in refs if isinstance(ref, dict) and ref.get("name"))


def _derive_stable_seed(parts: List[Optional[str]]) -> Optional[int]:
    seed_source = "|".join(str(part) for part in parts if part)
    if not seed_source:
        return None
    digest = hashlib.sha256(seed_source.encode("utf-8")).hexdigest()
    return (int(digest[:12], 16) % MAX_PROVIDER_SEED) or 1


def _resolve_video_seed(request: VideoGenerateRequest, lineage: dict, consistency_metadata: dict) -> Optional[int]:
    if request.seed is not None:
        return request.seed
    if consistency_metadata.get("seed") is not None:
        return consistency_metadata["seed"]
    if not request.use_consistency_context:
        return None
    return _derive_stable_seed([
        consistency_metadata.get("project_id") or lineage.get("project_id"),
        consistency_metadata.get("story_bible_id"),
        lineage.get("novel_id"),
        lineage.get("chapter_id"),
        lineage.get("script_id"),
        lineage.get("storyboard_id"),
        request.model,
    ])


def _build_video_context_metadata(
    lineage: dict,
    consistency_metadata: dict,
    seed: Optional[int],
    shot_context_override: Optional[dict] = None,
) -> dict:
    shot_context = shot_context_override or _extract_shot_generation_context(lineage.get("shot"))
    consistency = dict(consistency_metadata or {})
    if seed is not None:
        consistency["seed"] = seed
    if consistency.get("series_seed") is not None:
        consistency.setdefault("style_seed", consistency["series_seed"])
    return {
        **shot_context,
        "seed": seed,
        "series_seed": consistency.get("series_seed"),
        "novel_series_seed": consistency.get("novel_series_seed") or consistency.get("series_seed"),
        "chapter_seed": consistency.get("chapter_seed"),
        "storyboard_seed": consistency.get("storyboard_seed"),
        "style_lock": consistency.get("style_lock"),
        "continuity_lock": consistency.get("continuity_lock"),
        "previous_chapter_context": consistency.get("previous_chapter_context"),
        "current_chapter_context": consistency.get("current_chapter_context"),
        "next_chapter_constraint": consistency.get("next_chapter_constraint"),
        "previous_chapter_state": consistency.get("previous_chapter_state"),
        "chapter_state_snapshot": consistency.get("chapter_state_snapshot"),
        "state_machine_version": consistency.get("state_machine_version"),
        "state_machine_summary": consistency.get("state_machine_summary"),
        "event_timeline_tail": consistency.get("event_timeline_tail") or [],
        "entity_locks": consistency.get("entity_locks") or {},
        "character_visual_locks": consistency.get("character_visual_locks") or shot_context.get("character_refs") or [],
        "character_multiview_refs": consistency.get("character_multiview_refs") or shot_context.get("character_multiview_refs") or [],
        "reference_image_source": consistency.get("reference_image_source"),
        "invalid_entity_ref_count": consistency.get("invalid_entity_ref_count", 0),
        "consistency": consistency,
    }


def _build_video_extra_data(request: VideoGenerateRequest, lineage: dict) -> dict:
    """Build lineage metadata shared by real and DEV_MODE video jobs."""
    extra_data = {}
    if request.project_id:
        extra_data["project_id"] = request.project_id
    if request.workflow_id:
        extra_data["workflow_id"] = request.workflow_id
    for key in (
        "novel_id",
        "novel_title",
        "chapter_id",
        "chapter_title",
        "chapter_number",
        "script_id",
        "script_title",
        "storyboard_id",
        "storyboard_title",
        "shot_id",
        "shot_number",
    ):
        if lineage.get(key) is not None:
            extra_data[key] = lineage[key]
    return extra_data


def _build_video_job_response(job: VideoJob) -> VideoJobResponse:
    extra = _json_dict(job.extra_data)
    consistency = _json_dict(extra.get("consistency"))
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
    extra = _json_dict(job.extra_data)
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
    extra = _json_dict(job.extra_data)
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
        lineage = await _resolve_video_lineage(db, user_id, request)
        request = request.model_copy(update={
            "project_id": lineage.get("project_id"),
            "workflow_id": lineage.get("workflow_id"),
            "novel_id": lineage.get("novel_id"),
            "chapter_id": lineage.get("chapter_id"),
            "script_id": lineage.get("script_id"),
            "storyboard_id": lineage.get("storyboard_id"),
            "shot_id": lineage.get("shot_id"),
        })
        video_model_config = await _resolve_video_model_config(db, user_id, request.model, request.model_config_id)
        if video_model_config.get("provider_id") not in {"volcano", VOLCANO_AGENT_PLAN_PROVIDER_ID}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="静音视频生成当前只支持火山普通视频模型或火山方舟 Agent Plan 视频模型。Sora/Veo/ComfyUI 等生产适配请在本页切换到「直生音视频」，或在 workflow 中使用批量直生/云渲染。",
            )
        if not is_dev_mode() and not request.use_consistency_context and not request.unsafe_skip_consistency_preflight:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="生产模式不能跳过一致性预检；如需降级调试，请显式开启 unsafe_skip_consistency_preflight 并记录原因。",
            )

        final_prompt = request.prompt
        consistency_metadata = {}
        shot_context = _extract_shot_generation_context(lineage.get("shot"))
        effective_image_url = request.image_url
        reference_image_source = "request" if request.image_url else None
        preflight_package = None
        if request.use_consistency_context:
            package = await _build_video_consistency_package(
                db,
                user_id,
                request,
                lineage,
            )
            final_prompt = package["final_prompt"]
            consistency_metadata = package["metadata"]
            shot_context = package["context"]
            effective_image_url = package["reference_image"]
            reference_image_source = package["reference_image_source"]
        if not is_dev_mode() and not request.unsafe_skip_consistency_preflight:
            preflight_package = await build_generation_context_package(
                db,
                user_id,
                task_type="shot_video",
                model_config_id=request.model_config_id,
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
        video_seed = _resolve_video_seed(request, lineage, consistency_metadata)
        image_delivery = await _resolve_provider_image_delivery(db, user_id, effective_image_url)
        provider_image_url = image_delivery["provider_image_url"]
        image_url_omitted_reason = image_delivery["image_url_omitted_reason"]
        if image_url_omitted_reason:
            final_prompt = _append_provider_image_note(final_prompt, image_url_omitted_reason)
        context_metadata = _build_video_context_metadata(lineage, consistency_metadata, video_seed, shot_context)
        if preflight_package is not None:
            context_metadata["generation_preflight"] = {
                "ready": preflight_package.get("ready"),
                "issues": preflight_package.get("issues") or [],
                "blocking_issue_count": preflight_package.get("blocking_issue_count") or 0,
            }
        prompt_parameters = _video_prompt_parameters(
            request.model_copy(update={"image_url": effective_image_url}),
            video_seed,
            provider_image_url,
            image_url_omitted_reason,
            image_delivery["image_delivery"],
        )
        prompt_parameters["reference_image_source"] = reference_image_source
        supplemental_refs = shot_context.get("character_multiview_refs") or []
        prompt_parameters["provider_reference_image_limit"] = 1
        prompt_parameters["reference_image_strategy"] = (
            "single_provider_image_with_textual_asset_constraints"
            if supplemental_refs or (shot_context.get("asset_version_locks") or [])
            else "single_provider_image"
        )
        prompt_parameters["supplemental_reference_image_count"] = len(supplemental_refs)

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

        if not resolved_api_key and is_dev_mode():
            job_id = str(uuid4())
            task_id = f"dev-video-{job_id}"
            video_url = dev_video_url(job_id)
            extra_data = _build_video_extra_data(request, lineage)
            extra_data.update(context_metadata)
            extra_data.update(_video_model_metadata(video_model_config))
            extra_data["prompt_parameters"] = prompt_parameters
            extra_data["source_prompt"] = request.prompt
            job = VideoJob(
                id=job_id,
                user_id=user_id,
                project_id=request.project_id,
                workflow_id=request.workflow_id,
                task_id=task_id,
                title=request.prompt[:50] if len(request.prompt) > 50 else request.prompt,
                prompt=final_prompt,
                model_id=video_model_config.get("api_model_id") or request.model,
                model_name=f"{video_model_config.get('model_name') or _get_volcano_model_name(request.model)} (DEV_MODE)",
                duration=request.duration,
                resolution=request.resolution,
                image_url=effective_image_url,
                status="succeeded",
                progress=100,
                video_url=video_url,
                cover_url=effective_image_url,
                extra_data=extra_data,
            )
            db.add(job)
            await _attach_video_job_to_workflow(db, job, user_id)
            await _sync_video_job_and_shot(
                db=db,
                job=job,
                status_value="succeeded",
                progress=100,
                video_url=video_url,
                cover_url=effective_image_url,
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
        client = _create_ark_client(resolved_api_key, resolved_base_url)

        # 构建content
        content = []

        # 云端视频模型只能读取公网可访问图片；本地静态图继续保留在历史和提示词上下文中。
        if provider_image_url:
            content.append({
                "type": "image_url",
                "image_url": {"url": provider_image_url}
            })

        # 构建提示词，包含参数
        duration_arg = f"--duration {request.duration}"
        camerafixed = "false"  # 相机运动
        watermark = "true"
        resolution_arg = f"--resolution {request.resolution}"

        prompt_text = f"{final_prompt} {duration_arg} {resolution_arg} --camerafixed {camerafixed} --watermark {watermark}"

        content.append({
            "type": "text",
            "text": prompt_text
        })

        # 视频模型需要 endpoint_id，不是模型名。
        video_model = video_model_config.get("model_endpoint_id") or request.model

        # 调用SDK创建任务
        create_kwargs = {
            "model": video_model,
            "content": content,
            "duration": request.duration,
            "resolution": request.resolution,
            "camera_fixed": False,
            "watermark": True,
        }
        if video_seed is not None:
            create_kwargs["seed"] = video_seed
        try:
            create_result = client.content_generation.tasks.create(**create_kwargs)
        except Exception as exc:
            image_error = _provider_image_url_error_message(exc, provider_image_url)
            if image_error:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=image_error) from exc
            raise

        # 构建关联数据（ID + 标题）
        extra_data = _build_video_extra_data(request, lineage)
        extra_data.update(context_metadata)
        extra_data.update(_video_model_metadata(video_model_config))
        extra_data["prompt_parameters"] = prompt_parameters
        extra_data["source_prompt"] = request.prompt

        # 创建数据库记录
        job = VideoJob(
            id=str(uuid4()),
            user_id=user_id,
            project_id=request.project_id,
            workflow_id=request.workflow_id,
            task_id=create_result.id,
            title=request.prompt[:50] if len(request.prompt) > 50 else request.prompt,
            prompt=final_prompt,
            model_id=video_model_config.get("api_model_id") or request.model,
            model_name=video_model_config.get("model_name") or _get_volcano_model_name(request.model),
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
        provider_for_status = (_json_dict(existing_job.extra_data).get("provider_id") or "volcano")

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
        client = _create_ark_client(resolved_api_key, resolved_base_url)
        
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
            await _sync_video_job_and_shot(
                db=db,
                job=job_record,
                status_value=mapped_status,
                progress=progress,
                video_url=video_url,
                cover_url=cover_url,
                error_message=str(getattr(get_result, "error", "")) if mapped_status == "failed" else None,
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
        provider_for_refresh = _json_dict(job.extra_data).get("provider_id") or "volcano"
        resolved_api_key, resolved_base_url = await get_user_api_key(db, user_id, provider_for_refresh)
        client = _create_ark_client(resolved_api_key, resolved_base_url)
        
        get_result = client.content_generation.tasks.get(task_id=job.task_id)
        task_status = get_result.status
        
        # 更新状态
        job.status = task_status
        
        if task_status == "succeeded":
            job.progress = 100
            video_url, cover_url = _extract_video_result(get_result)
            await _sync_video_job_and_shot(
                db=db,
                job=job,
                status_value=task_status,
                progress=100,
                video_url=video_url,
                cover_url=cover_url,
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
            await _sync_video_job_and_shot(db, job, task_status, 50, None, None)
        elif task_status == "failed":
            await _sync_video_job_and_shot(
                db,
                job,
                task_status,
                100,
                None,
                None,
                str(getattr(get_result, 'error', 'Unknown error')),
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
        await _sync_video_job_and_shot(
            db=db,
            job=job,
            status_value=job.status,
            progress=job.progress or 0,
            video_url=None,
            cover_url=None,
            error_message=job.error_message,
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
    await _sync_video_job_and_shot(
        db=db,
        job=job,
        status_value="cancelled",
        progress=job.progress,
        video_url=None,
        cover_url=None,
        error_message=job.error_message,
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
