"""
大模型配置API
支持多模型接入配置管理
"""

from app.core.time_utils import utc_now
from typing import List, Optional
from datetime import datetime
from uuid import uuid4
import httpx  # Compatibility alias for legacy tests; provider logic lives in model_drivers.
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, desc
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.model_registry import (
    get_registry,
    get_task_default,
    get_video_model_catalog,
)
from app.core.security import get_current_user_id
from app.core.volcano_image_catalog import VOLCANO_IMAGE_MODEL_SEEDS
from app.core.volcano_agent_plan_config import (
    VOLCANO_AGENT_PLAN_MODELS,
    VOLCANO_AGENT_PLAN_PROVIDER,
)
from app.features.model_config.credential_persistence import (
    apply_config_update,
    apply_create_or_upsert_config,
)
from app.features.model_config.management_repository import binding_page
from app.features.model_config.public import (
    is_product_visible_model,
    is_product_visible_provider,
    legacy_model_capability_group,
    maybe_log_shadow_catalog_comparison,
    project_legacy_llm_models,
)
from app.features.model_drivers import (
    execute_llm_connection_test,
    resolve_published_driver_key,
    test_minimax_api,
    test_volcano_agent_plan_api,
    test_volcano_api,
)
from app.models.llm_config import LLMProvider, LLMModel, LLMConfig, LLMUsageLog
from app.services.deterministic_provider_fake import (
    deterministic_config_test_result,
    deterministic_provider_fake_enabled,
)
from app.services.volcano_speech_tts import configure_volcano_speech_endpoint
router = APIRouter(tags=["大模型配置"])
logger = logging.getLogger(__name__)


@router.get("/registry")
async def get_model_registry():
    """获取统一模型注册表。

    该接口为前端提供文本、图像、声音、视频模型的统一规划；用户 API Key
    仍通过 `/llm/configs` 管理。
    """
    return get_registry()


@router.get("/task-defaults")
async def list_task_defaults():
    """获取所有生产任务的默认模型选择。"""
    registry = get_registry()
    return {"task_defaults": registry["task_defaults"]}


@router.get("/task-defaults/{task}")
async def get_task_default_model(task: str):
    """获取单个任务的默认模型选择。"""
    task_default = get_task_default(task)
    if task_default is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务默认模型不存在")
    return task_default


# ============== 请求/响应模型 ==============

class LLMProviderResponse(BaseModel):
    """提供商响应"""
    id: str
    name: str
    name_cn: str
    name_en: str
    provider_type: str
    base_url: str
    is_active: bool
    description: Optional[str]
    icon_url: Optional[str]


class LLMModelResponse(BaseModel):
    """模型响应"""
    id: str
    provider_id: str
    model_id: str
    model_name: str
    model_name_cn: Optional[str]
    model_type: str
    capabilities: List[str]
    context_window: int
    max_tokens: int
    input_cost_per_1k: float
    output_cost_per_1k: float
    is_active: bool
    is_recommended: bool
    description: Optional[str]
    base_url: Optional[str] = None
    user_config_id: Optional[str] = None
    user_config_name: Optional[str] = None
    user_configured: bool = False
    user_config_count: int = 0
    user_is_default: bool = False
    user_test_status: Optional[str] = None
    user_test_message: Optional[str] = None
    user_key_available: bool = False
    contract_status: str = "unavailable"
    contract_version: str = "legacy-single-reference-v1"
    verified_at: Optional[str] = None
    reference_limits: dict = Field(default_factory=dict)
    verification_gaps: List[str] = Field(default_factory=list)


class LLMConfigCreateRequest(BaseModel):
    """创建配置请求"""
    model_id: str = Field(..., description="模型ID")
    name: str = Field(..., min_length=1, max_length=100, description="配置名称")
    api_key: str = Field(..., description="API密钥")
    api_secret: Optional[str] = Field(None, description="API Secret")
    temperature: float = Field(0.7, ge=0, le=2)
    top_p: float = Field(0.9, ge=0, le=1)
    max_tokens: Optional[int] = Field(None, ge=1, le=32000)
    extra_params: Optional[dict] = Field({}, description="额外参数")
    is_default: bool = Field(False, description="设为默认")


class LLMConfigUpdateRequest(BaseModel):
    """更新配置请求。API Key 不传或传空时保留原密钥。"""
    model_id: str = Field(..., description="模型ID")
    name: str = Field(..., min_length=1, max_length=100, description="配置名称")
    api_key: Optional[str] = Field(None, description="API密钥")
    api_secret: Optional[str] = Field(None, description="API Secret")
    temperature: float = Field(0.7, ge=0, le=2)
    top_p: float = Field(0.9, ge=0, le=1)
    max_tokens: Optional[int] = Field(None, ge=1, le=32000)
    extra_params: Optional[dict] = Field({}, description="额外参数")
    is_default: bool = Field(False, description="设为默认")


class LLMConfigResponse(BaseModel):
    """配置响应"""
    id: str
    user_id: str
    model_id: str
    config_model_id: Optional[str] = None
    api_model_id: Optional[str] = None
    model_type: Optional[str] = None
    model_capabilities: List[str] = Field(default_factory=list)
    provider_id: str  # 前端用于判断配置属于哪个服务商
    model_name: str
    provider_name: str
    name: str
    temperature: float
    top_p: float
    max_tokens: Optional[int]
    is_active: bool
    is_default: bool
    test_status: Optional[str]
    test_message: Optional[str]
    key_available: bool = False
    usage_count: int
    created_at: datetime
    updated_at: datetime


class LLMTestRequest(BaseModel):
    """测试请求"""
    api_key: Optional[str] = Field(None, description="API密钥")
    provider_id: Optional[str] = Field(None, description="提供商ID")
    model_id: Optional[str] = Field(None, description="模型ID")
    message: str = Field("你好，请介绍一下自己", description="测试消息")


class LLMTestResponse(BaseModel):
    """测试响应"""
    success: bool
    message: str
    response: Optional[str]
    response_time_ms: Optional[int]
    tokens_used: Optional[int]


def build_llm_config_response(config: LLMConfig, model: LLMModel, provider: Optional[LLMProvider]) -> dict:
    provider_id = provider.name if provider else model.provider_id
    key_available = bool(config.get_api_key_decrypted())
    test_status = config.test_status
    test_message = config.test_message
    if not key_available:
        test_status = "failed"
        test_message = "API Key 为空或无法解密，请重新保存并验证该配置"
    return {
        "id": config.id,
        "user_id": config.user_id,
        "model_id": model.model_id,
        "config_model_id": config.model_id,
        "api_model_id": model.model_id,
        "model_type": model.model_type,
        "model_capabilities": model.capabilities or [],
        "provider_id": provider_id,
        "model_name": model.model_name_cn or model.model_name,
        "provider_name": provider.name_cn if provider else "未知",
        "name": config.name,
        "temperature": config.temperature,
        "top_p": config.top_p,
        "max_tokens": config.max_tokens,
        "is_active": config.is_active,
        "is_default": config.is_default,
        "test_status": test_status,
        "test_message": test_message,
        "key_available": key_available,
        "usage_count": config.usage_count,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }


def canonical_text_default_config(user_id: str, bindings: list[dict]) -> dict | None:
    candidates = [item for item in bindings if (
        item.get("is_active")
        and item.get("scope_type") == "user"
        and item.get("scope_id") == user_id
        and item.get("task") == "script_generation"
        and item.get("capability") == "text_generation"
    )]
    if not candidates:
        return None
    binding = max(candidates, key=lambda item: (item.get("version", 0), item.get("priority", 0)))
    verified = binding.get("certification_status") == "success"
    now = utc_now()
    return {
        "id": "", "user_id": user_id, "model_id": binding["profile_version_id"],
        "config_model_id": None, "api_model_id": binding["api_model_id"],
        "model_type": "chat", "model_capabilities": ["text_generation"],
        "provider_id": binding["connection_id"], "model_name": binding["profile_name"],
        "provider_name": binding["provider_name"], "name": binding["api_model_id"],
        "temperature": 0.7, "top_p": 0.9, "max_tokens": None,
        "is_active": True, "is_default": True, "test_status": binding["certification_status"],
        "test_message": None, "key_available": verified, "usage_count": 0,
        "created_at": now, "updated_at": now,
    }


async def clear_default_configs_for_model_group(
    db: AsyncSession,
    user_id: str,
    model: LLMModel,
    *,
    exclude_config_id: Optional[str] = None,
) -> None:
    """Keep one default per capability group, not one global default."""
    group = legacy_model_capability_group(model)
    result = await db.execute(
        select(LLMConfig, LLMModel)
        .join(LLMModel, LLMConfig.model_id == LLMModel.id)
        .where(
            and_(
                LLMConfig.user_id == user_id,
                LLMConfig.is_active == True,
                LLMConfig.is_default == True,
            )
        )
    )
    for config, existing_model in result.all():
        if exclude_config_id and config.id == exclude_config_id:
            continue
        if legacy_model_capability_group(existing_model) == group:
            config.is_default = False


# ============== 预设数据 ==============

def _video_catalog_model_seeds() -> list[dict]:
    seeds = []
    for model in get_video_model_catalog("shot_video")["models"]:
        status_info = model.get("status") if isinstance(model.get("status"), dict) else {}
        seeds.append({
            "id": model["id"],
            "provider_id": model["provider_id"],
            "model_id": model["api_model_id"],
            "model_name": model["display_name"],
            "model_name_cn": model["display_name"],
            "model_type": "video-generation",
            "capabilities": model.get("capabilities") or [],
            "context_window": 0,
            "max_tokens": 0,
            "input_cost_per_1k": 0,
            "output_cost_per_1k": 0,
            "supports_streaming": False,
            "supports_function_calling": False,
            "supports_vision": False,
            "supports_json_mode": False,
            "is_active": status_info.get("active", True),
            "is_recommended": status_info.get("recommended", False),
            "description": f"{model.get('display_name')} 视频生成模型，{model.get('routing', {}).get('lane', 'catalog')} 路线",
            "version": model["id"].rsplit(".", 1)[-1],
        })
    return seeds


DEFAULT_PROVIDERS = [
    {
        "id": "volcano",
        "name": "volcano",
        "name_cn": "火山引擎",
        "name_en": "Volcano Engine",
        "provider_type": "cloud",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "auth_type": "bearer",
        "description": "字节跳动旗下云服务平台，提供豆包大模型",
        "icon_url": "/icons/volcano.svg",
        "website_url": "https://www.volcengine.com",
        "doc_url": "https://www.volcengine.com/docs/82379"
    },
    VOLCANO_AGENT_PLAN_PROVIDER,
    {
        "id": "qwen",
        "name": "qwen",
        "name_cn": "阿里千问",
        "name_en": "Alibaba Qwen",
        "provider_type": "cloud",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "auth_type": "bearer",
        "description": "阿里云通义千问大模型",
        "icon_url": "/icons/qwen.svg",
        "website_url": "https://dashscope.console.aliyun.com",
        "doc_url": "https://help.aliyun.com/document_detail/611411.html"
    },
    {
        "id": "baidu",
        "name": "baidu",
        "name_cn": "百度文心一言",
        "name_en": "Baidu ERNIE",
        "provider_type": "cloud",
        "base_url": "https://qianfan.baidubce.com/v2/chat/completions",
        "auth_type": "bearer",
        "description": "百度文心一言大模型，支持ERNIE-4.0、ERNIE-3.5等模型",
        "icon_url": "/icons/baidu.svg",
        "website_url": "https://console.bce.baidu.com/qianfan",
        "doc_url": "https://cloud.baidu.com/doc/WenxinWorkshop/index.html"
    },
    {
        "id": "openai",
        "name": "openai",
        "name_cn": "OpenAI",
        "name_en": "OpenAI",
        "provider_type": "cloud",
        "base_url": "https://api.openai.com/v1",
        "auth_type": "bearer",
        "description": "OpenAI 提供 GPT-4o、DALL-E、Sora 等模型",
        "icon_url": "/icons/openai.svg",
        "website_url": "https://platform.openai.com/",
        "doc_url": "https://platform.openai.com/docs"
    },
    {
        "id": "alibaba",
        "name": "alibaba",
        "name_cn": "阿里视频",
        "name_en": "Alibaba Video",
        "provider_type": "cloud",
        "base_url": "https://dashscope.aliyuncs.com",
        "auth_type": "bearer",
        "description": "阿里系视频生成模型，预留 HappyHorse 等视频模型配置",
        "icon_url": "/icons/qwen.svg",
        "website_url": "https://dashscope.console.aliyun.com",
        "doc_url": "https://help.aliyun.com/document_detail/611411.html"
    },
    {
        "id": "kling",
        "name": "kling",
        "name_cn": "可灵",
        "name_en": "Kling AI",
        "provider_type": "cloud",
        "base_url": "https://api.klingai.com",
        "auth_type": "bearer",
        "description": "可灵视频生成模型，支持 3.0 Omni、V2.6、O1 等路线",
        "icon_url": "/icons/kling.svg",
        "website_url": "https://klingai.com",
        "doc_url": "https://klingai.com"
    },
    {
        "id": "pixverse",
        "name": "pixverse",
        "name_cn": "PixVerse / 拍我",
        "name_en": "PixVerse",
        "provider_type": "cloud",
        "base_url": "https://app-api.pixverse.ai/openapi/v2",
        "auth_type": "bearer",
        "description": "PixVerse / 拍我视频生成模型，适合动漫动作与特效镜头",
        "icon_url": "/icons/pixverse.svg",
        "website_url": "https://pixverse.ai",
        "doc_url": "https://pixverse.ai"
    },
    {
        "id": "minimax",
        "name": "minimax",
        "name_cn": "MiniMax",
        "name_en": "MiniMax",
        "provider_type": "cloud",
        "base_url": "https://api.minimaxi.com/v1",
        "auth_type": "bearer",
        "description": "MiniMax 海螺AI，支持文本生成、图像生成、TTS语音合成",
        "icon_url": "/icons/minimax.svg",
        "website_url": "https://www.minimaxi.com/",
        "doc_url": "https://platform.minimaxi.com/document"
    }
]

DEFAULT_MODELS = [
    *VOLCANO_AGENT_PLAN_MODELS,
    *_video_catalog_model_seeds(),
    # 火山引擎模型
    {
        "id": "doubao-seed-1-8",
        "provider_id": "volcano",
        "model_id": "doubao-seed-1-8-251228",
        "model_name": "Doubao-Seed-1.8",
        "model_name_cn": "豆包Seed-1.8",
        "model_type": "chat",
        "capabilities": ["chat", "completion", "function_calling", "json_mode"],
        "context_window": 4096,
        "max_tokens": 2048,
        "input_cost_per_1k": 0.005,
        "output_cost_per_1k": 0.009,
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "supports_json_mode": True,
        "is_active": True,
        "is_recommended": True,
        "description": "豆包最新轻量级模型，性价比高",
        "version": "1.8",
        "release_date": "2024-12-28"
    },
    {
        "id": "doubao-pro-4k",
        "provider_id": "volcano",
        "model_id": "doubao-pro-4k",
        "model_name": "Doubao-Pro-4K",
        "model_name_cn": "豆包Pro-4K",
        "model_type": "chat",
        "capabilities": ["chat", "completion", "function_calling"],
        "context_window": 4096,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.008,
        "output_cost_per_1k": 0.02,
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "supports_json_mode": False,
        "is_active": True,
        "is_recommended": False,
        "description": "豆包Pro轻量版，性价比高",
        "version": "1.0",
        "release_date": "2024-06-01"
    },
    {
        "id": "doubao-lite-4k",
        "provider_id": "volcano",
        "model_id": "doubao-lite-4k",
        "model_name": "Doubao-Lite-4K",
        "model_name_cn": "豆包Lite-4K",
        "model_type": "chat",
        "capabilities": ["chat", "completion"],
        "context_window": 4096,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.003,
        "output_cost_per_1k": 0.006,
        "supports_streaming": True,
        "supports_function_calling": False,
        "supports_vision": False,
        "supports_json_mode": False,
        "is_active": True,
        "is_recommended": False,
        "description": "豆包Lite极速版，响应最快，成本最低",
        "version": "1.0",
        "release_date": "2024-06-01"
    },
    {
        "id": "doubao-pro-32k",
        "provider_id": "volcano",
        "model_id": "doubao-pro-32k",
        "model_name": "Doubao-Pro-32K",
        "model_name_cn": "豆包Pro-32K",
        "model_type": "chat",
        "capabilities": ["chat", "completion", "function_calling", "json_mode"],
        "context_window": 32768,
        "max_tokens": 8192,
        "input_cost_per_1k": 0.02,
        "output_cost_per_1k": 0.06,
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "supports_json_mode": True,
        "is_active": True,
        "is_recommended": False,
        "description": "豆包Pro长上下文版，支持32K上下文",
        "version": "1.0",
        "release_date": "2024-06-01"
    },
    # 火山引擎图像/视频生成模型
    *VOLCANO_IMAGE_MODEL_SEEDS,
    {
        "id": "doubao-seed-2.0-pro",
        "provider_id": "volcano",
        "model_id": "Doubao-Seed-2.0-pro",
        "model_name": "Doubao-Seed-2.0-pro",
        "model_name_cn": "豆包Seed-2.0-pro",
        "model_type": "chat",
        "capabilities": ["chat", "completion", "function_calling", "json_mode"],
        "context_window": 4096,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.5,
        "output_cost_per_1k": 0.5,
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "supports_json_mode": True,
        "is_active": True,
        "is_recommended": False,
        "description": "火山引擎豆包 Seed 2.0 文本模型",
        "version": "2.0-pro",
        "release_date": "2026-03-01",
        "endpoint_id": "ep-20260320111926-sn9tg"
    },
    {
        "id": "doubao-seedance-2.0",
        "provider_id": "volcano",
        "model_id": "doubao-seedance-2-0-260128",
        "model_name": "Doubao-Seedance-2.0",
        "model_name_cn": "豆包Seedance-2.0",
        "model_type": "video-generation",
        "capabilities": ["text-to-video", "image-to-video"],
        "context_window": 0,
        "max_tokens": 0,
        "input_cost_per_1k": 0,
        "output_cost_per_1k": 0,
        "supports_streaming": False,
        "supports_function_calling": False,
        "supports_vision": False,
        "supports_json_mode": False,
        "is_active": True,
        "is_recommended": True,
        "description": "豆包Seedance 2.0，高质量视频生成，支持文生视频、图生视频",
        "version": "2.0",
        "release_date": "2026-01-28",
        "endpoint_id": "doubao-seedance-2-0-260128"
    },
    {
        "id": "doubao-seedance-2.0-fast",
        "provider_id": "volcano",
        "model_id": "doubao-seedance-2-0-fast-260128",
        "model_name": "Doubao-Seedance-2.0-fast",
        "model_name_cn": "豆包Seedance-2.0-fast",
        "model_type": "video-generation",
        "capabilities": ["text-to-video", "image-to-video"],
        "context_window": 0,
        "max_tokens": 0,
        "input_cost_per_1k": 0,
        "output_cost_per_1k": 0,
        "supports_streaming": False,
        "supports_function_calling": False,
        "supports_vision": False,
        "supports_json_mode": False,
        "is_active": True,
        "is_recommended": True,
        "description": "豆包Seedance 2.0 Fast，适合批量镜头草稿和快速预览",
        "version": "2.0-fast",
        "release_date": "2026-01-28",
        "endpoint_id": "doubao-seedance-2-0-fast-260128"
    },
    # 千问模型
    {
        "id": "qwen-turbo",
        "provider_id": "qwen",
        "model_id": "qwen-turbo",
        "model_name": "Qwen-Turbo",
        "model_name_cn": "千问Turbo",
        "model_type": "chat",
        "capabilities": ["chat", "completion"],
        "context_window": 8192,
        "max_tokens": 2048,
        "input_cost_per_1k": 0.005,
        "output_cost_per_1k": 0.01,
        "supports_streaming": True,
        "supports_function_calling": False,
        "supports_vision": False,
        "supports_json_mode": False,
        "is_active": True,
        "is_recommended": True,
        "description": "轻量级模型，响应速度快，成本低",
        "version": "1.0",
        "release_date": "2024-01-01"
    },
    {
        "id": "qwen-plus",
        "provider_id": "qwen",
        "model_id": "qwen-plus",
        "model_name": "Qwen-Plus",
        "model_name_cn": "千问Plus",
        "model_type": "chat",
        "capabilities": ["chat", "completion", "function_calling"],
        "context_window": 32768,
        "max_tokens": 8192,
        "input_cost_per_1k": 0.02,
        "output_cost_per_1k": 0.06,
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "supports_json_mode": True,
        "is_active": True,
        "is_recommended": True,
        "description": "均衡型模型，综合能力优秀",
        "version": "1.0",
        "release_date": "2024-06-01"
    },
    {
        "id": "qwen-max",
        "provider_id": "qwen",
        "model_id": "qwen-max",
        "model_name": "Qwen-Max",
        "model_name_cn": "千问Max",
        "model_type": "chat",
        "capabilities": ["chat", "completion", "function_calling", "json_mode"],
        "context_window": 32768,
        "max_tokens": 8192,
        "input_cost_per_1k": 0.2,
        "output_cost_per_1k": 0.6,
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "supports_json_mode": True,
        "is_active": True,
        "is_recommended": False,
        "description": "旗舰级模型，最强性能",
        "version": "1.0",
        "release_date": "2024-06-01"
    },
    {
        "id": "qwen-long",
        "provider_id": "qwen",
        "model_id": "qwen-long",
        "model_name": "Qwen-Long",
        "model_name_cn": "千问Long",
        "model_type": "chat",
        "capabilities": ["chat", "completion"],
        "context_window": 1000000,
        "max_tokens": 8192,
        "input_cost_per_1k": 0.005,
        "output_cost_per_1k": 0.02,
        "supports_streaming": True,
        "supports_function_calling": False,
        "supports_vision": False,
        "supports_json_mode": False,
        "is_active": True,
        "is_recommended": False,
        "description": "超长上下文模型，支持百万token",
        "version": "1.0",
        "release_date": "2024-06-01"
    },
    {
        "id": "qwen-coder-plus",
        "provider_id": "qwen",
        "model_id": "qwen-coder-plus",
        "model_name": "Qwen-Coder-Plus",
        "model_name_cn": "千问Coder Plus",
        "model_type": "chat",
        "capabilities": ["chat", "completion", "code_generation", "planning"],
        "context_window": 32768,
        "max_tokens": 8192,
        "input_cost_per_1k": 0.02,
        "output_cost_per_1k": 0.06,
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "supports_json_mode": True,
        "is_active": True,
        "is_recommended": True,
        "description": "代码生成旗舰模型，支持复杂规划和架构设计",
        "version": "1.0",
        "release_date": "2024-06-01"
    },
    {
        "id": "qwen-vl-plus",
        "provider_id": "qwen",
        "model_id": "qwen-vl-plus",
        "model_name": "Qwen-VL-Plus",
        "model_name_cn": "千问VL Plus",
        "model_type": "vision",
        "capabilities": ["chat", "vision", "image_understanding"],
        "context_window": 32768,
        "max_tokens": 2048,
        "input_cost_per_1k": 0.02,
        "output_cost_per_1k": 0.06,
        "supports_streaming": True,
        "supports_function_calling": False,
        "supports_vision": True,
        "supports_json_mode": False,
        "is_active": True,
        "is_recommended": False,
        "description": "视觉语言模型，支持图像理解",
        "version": "1.0",
        "release_date": "2024-06-01"
    },
    # 百度文心一言模型
    {
        "id": "ernie-4.0-8k",
        "provider_id": "baidu",
        "model_id": "ernie-4.0-8k",
        "model_name": "ERNIE-4.0-8K",
        "model_name_cn": "文心一言4.0-8K",
        "model_type": "chat",
        "capabilities": ["chat", "completion", "function_calling", "json_mode"],
        "context_window": 8192,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.12,
        "output_cost_per_1k": 0.12,
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "supports_json_mode": True,
        "is_active": True,
        "is_recommended": True,
        "description": "百度文心旗舰大模型，知识理解与生成能力强",
        "version": "4.0",
        "release_date": "2024-05-01"
    },
    {
        "id": "ernie-3.5-8k",
        "provider_id": "baidu",
        "model_id": "ernie-3.5-8k",
        "model_name": "ERNIE-3.5-8K",
        "model_name_cn": "文心一言3.5-8K",
        "model_type": "chat",
        "capabilities": ["chat", "completion", "function_calling", "json_mode"],
        "context_window": 8192,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.012,
        "output_cost_per_1k": 0.012,
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "supports_json_mode": True,
        "is_active": True,
        "is_recommended": True,
        "description": "文心3.5升级版，性价比高",
        "version": "3.5",
        "release_date": "2024-03-01"
    },
    {
        "id": "ernie-3.5-8k-0205",
        "provider_id": "baidu",
        "model_id": "ernie-3.5-8k-0205",
        "model_name": "ERNIE-3.5-8K-0205",
        "model_name_cn": "文心一言3.5-0205",
        "model_type": "chat",
        "capabilities": ["chat", "completion", "function_calling"],
        "context_window": 8192,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.008,
        "output_cost_per_1k": 0.008,
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "supports_json_mode": False,
        "is_active": True,
        "is_recommended": False,
        "description": "文心3.5轻量版，成本更低",
        "version": "3.5",
        "release_date": "2024-02-05"
    },
    {
        "id": "ernie-speed-8k",
        "provider_id": "baidu",
        "model_id": "ernie-speed-8k",
        "model_name": "ERNIE-Speed-8K",
        "model_name_cn": "文心一言Speed-8K",
        "model_type": "chat",
        "capabilities": ["chat", "completion"],
        "context_window": 8192,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.004,
        "output_cost_per_1k": 0.004,
        "supports_streaming": True,
        "supports_function_calling": False,
        "supports_vision": False,
        "supports_json_mode": False,
        "is_active": True,
        "is_recommended": True,
        "description": "文心极速版，响应速度快",
        "version": "speed",
        "release_date": "2024-05-01"
    },
    {
        "id": "ernie-lite-8k",
        "provider_id": "baidu",
        "model_id": "ernie-lite-8k",
        "model_name": "ERNIE-Lite-8K",
        "model_name_cn": "文心一言Lite-8K",
        "model_type": "chat",
        "capabilities": ["chat", "completion"],
        "context_window": 8192,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.003,
        "output_cost_per_1k": 0.003,
        "supports_streaming": True,
        "supports_function_calling": False,
        "supports_vision": False,
        "supports_json_mode": False,
        "is_active": True,
        "is_recommended": False,
        "description": "文心轻量版，成本最低",
        "version": "lite",
        "release_date": "2024-03-01"
    },
    # OpenAI - 文本模型
    {
        "id": "openai-gpt-4o",
        "provider_id": "openai",
        "model_id": "gpt-4o",
        "model_name": "GPT-4o",
        "model_name_cn": "GPT-4o",
        "model_type": "chat",
        "capabilities": ["chat", "vision", "function_calling", "json_mode"],
        "context_window": 128000,
        "max_tokens": 16384,
        "input_cost_per_1k": 2.5,
        "output_cost_per_1k": 10.0,
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "supports_json_mode": True,
        "is_active": True,
        "is_recommended": True,
        "description": "OpenAI 最强旗舰模型，支持文本和图像理解",
        "version": "2024-05-13",
        "release_date": "2024-05-13"
    },
    {
        "id": "openai-gpt-4o-mini",
        "provider_id": "openai",
        "model_id": "gpt-4o-mini",
        "model_name": "GPT-4o-mini",
        "model_name_cn": "GPT-4o-mini",
        "model_type": "chat",
        "capabilities": ["chat", "vision", "function_calling", "json_mode"],
        "context_window": 128000,
        "max_tokens": 16384,
        "input_cost_per_1k": 0.15,
        "output_cost_per_1k": 0.60,
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "supports_json_mode": True,
        "is_active": True,
        "is_recommended": True,
        "description": "轻量级旗舰模型，性价比高，支持文本和图像理解",
        "version": "2024-07-18",
        "release_date": "2024-07-18"
    },
    {
        "id": "openai-gpt-4-turbo",
        "provider_id": "openai",
        "model_id": "gpt-4-turbo",
        "model_name": "GPT-4-Turbo",
        "model_name_cn": "GPT-4 Turbo",
        "model_type": "chat",
        "capabilities": ["chat", "vision", "function_calling", "json_mode"],
        "context_window": 128000,
        "max_tokens": 4096,
        "input_cost_per_1k": 10.0,
        "output_cost_per_1k": 30.0,
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "supports_json_mode": True,
        "is_active": True,
        "is_recommended": False,
        "description": "GPT-4 高性能版，上下文窗口大",
        "version": "2024-04-09",
        "release_date": "2024-04-09"
    },
    {
        "id": "openai-gpt-3-5-turbo",
        "provider_id": "openai",
        "model_id": "gpt-3.5-turbo",
        "model_name": "GPT-3.5-Turbo",
        "model_name_cn": "GPT-3.5 Turbo",
        "model_type": "chat",
        "capabilities": ["chat", "function_calling", "json_mode"],
        "context_window": 16385,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.5,
        "output_cost_per_1k": 1.5,
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "supports_json_mode": True,
        "is_active": True,
        "is_recommended": False,
        "description": "轻量快速模型，适合简单任务",
        "version": "0125",
        "release_date": "2024-01-25"
    },
    # OpenAI - 图像生成模型
    {
        "id": "openai-dall-e-3",
        "provider_id": "openai",
        "model_id": "dall-e-3",
        "model_name": "DALL-E-3",
        "model_name_cn": "DALL-E 3",
        "model_type": "image-generation",
        "capabilities": ["text-to-image"],
        "context_window": 4096,
        "max_tokens": 4096,
        "input_cost_per_1k": 0,
        "output_cost_per_1k": 0,
        "supports_streaming": False,
        "supports_function_calling": False,
        "supports_vision": False,
        "supports_json_mode": False,
        "is_active": True,
        "is_recommended": True,
        "description": "OpenAI 高质量图像生成模型，支持精细控制和多种尺寸",
        "version": "3",
        "release_date": "2023-11-06"
    },
    {
        "id": "openai-dall-e-2",
        "provider_id": "openai",
        "model_id": "dall-e-2",
        "model_name": "DALL-E-2",
        "model_name_cn": "DALL-E 2",
        "model_type": "image-generation",
        "capabilities": ["text-to-image", "image-edit", "variation"],
        "context_window": 4096,
        "max_tokens": 4096,
        "input_cost_per_1k": 0,
        "output_cost_per_1k": 0,
        "supports_streaming": False,
        "supports_function_calling": False,
        "supports_vision": False,
        "supports_json_mode": False,
        "is_active": True,
        "is_recommended": False,
        "description": "OpenAI 图像生成模型，支持图像编辑和变体生成",
        "version": "2",
        "release_date": "2022-11-03"
    },
    # OpenAI - 视频生成模型 (Sora, 预留)
    {
        "id": "openai-sora",
        "provider_id": "openai",
        "model_id": "sora",
        "model_name": "Sora",
        "model_name_cn": "OpenAI Sora",
        "model_type": "video-generation",
        "capabilities": ["text-to-video", "image-to-video"],
        "context_window": 0,
        "max_tokens": 0,
        "input_cost_per_1k": 0,
        "output_cost_per_1k": 0,
        "supports_streaming": False,
        "supports_function_calling": False,
        "supports_vision": False,
        "supports_json_mode": False,
        "is_active": True,
        "is_recommended": False,
        "description": "OpenAI 视频生成模型（即将发布）",
        "version": "1.0",
        "release_date": "2024-02-15"
    },
    # MiniMax - 文本生成模型
    {
        "id": "minimax-m3",
        "provider_id": "minimax",
        "model_id": "MiniMax-M3",
        "model_name": "MiniMax-M3",
        "model_name_cn": "MiniMax-M3",
        "model_type": "chat",
        "capabilities": ["chat", "completion", "function_calling", "json_mode", "reasoning", "vision", "multimodal", "long_context"],
        "context_window": 1000000,
        "max_tokens": 8192,
        "input_cost_per_1k": 0,
        "output_cost_per_1k": 0,
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "supports_json_mode": True,
        "is_active": True,
        "is_recommended": True,
        "description": "MiniMax M3 最新文本/多模态模型，1M 上下文，适合小说、剧本、角色提取、分镜规划和多模态理解",
        "version": "M3",
        "release_date": "2026-06-01",
        "base_url": "https://api.minimaxi.com/v1"
    },
    {
        "id": "minimax-m2.7",
        "provider_id": "minimax",
        "model_id": "MiniMax-M2.7",
        "model_name": "MiniMax-M2.7",
        "model_name_cn": "MiniMax-M2.7",
        "model_type": "chat",
        "capabilities": ["chat", "completion", "function_calling", "json_mode", "reasoning"],
        "context_window": 1000000,
        "max_tokens": 8192,
        "input_cost_per_1k": 0,
        "output_cost_per_1k": 0,
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "supports_json_mode": True,
        "is_active": True,
        "is_recommended": False,
        "description": "MiniMax 最新旗舰模型，超长上下文，支持函数调用和推理",
        "version": "M2.7",
        "release_date": "2025-01-01"
    },
    # MiniMax - 图像生成模型
    {
        "id": "minimax-image-01",
        "provider_id": "minimax",
        "model_id": "image-01",
        "model_name": "MiniMax-image-01",
        "model_name_cn": "MiniMax图像生成",
        "model_type": "image-generation",
        "capabilities": ["text-to-image"],
        "context_window": 0,
        "max_tokens": 0,
        "input_cost_per_1k": 0,
        "output_cost_per_1k": 0,
        "supports_streaming": False,
        "supports_function_calling": False,
        "supports_vision": False,
        "supports_json_mode": False,
        "is_active": True,
        "is_recommended": True,
        "description": "MiniMax 高质量图像生成，支持文生图/图生图，生成快速",
        "version": "image-01",
        "release_date": "2025-01-01"
    },
    # MiniMax - TTS语音合成模型
    {
        "id": "minimax-speech-2.6-hd",
        "provider_id": "minimax",
        "model_id": "speech-2.6-hd",
        "model_name": "MiniMax-speech-2.6-hd",
        "model_name_cn": "MiniMax语音合成-HD",
        "model_type": "tts",
        "capabilities": ["text-to-speech"],
        "context_window": 0,
        "max_tokens": 0,
        "input_cost_per_1k": 0,
        "output_cost_per_1k": 0,
        "supports_streaming": False,
        "supports_function_calling": False,
        "supports_vision": False,
        "supports_json_mode": False,
        "is_active": True,
        "is_recommended": True,
        "description": "MiniMax 高质量语音合成，支持中文/英文/多语种，多种音色可选",
        "version": "speech-2.6-hd",
        "release_date": "2025-01-01"
    }
]


# ============== 辅助函数 ==============

_LLM_MODEL_COLUMNS = {
    "id",
    "provider_id",
    "model_id",
    "model_name",
    "model_name_cn",
    "model_type",
    "capabilities",
    "context_window",
    "max_tokens",
    "input_cost_per_1k",
    "output_cost_per_1k",
    "supports_streaming",
    "supports_function_calling",
    "supports_vision",
    "supports_json_mode",
    "is_active",
    "is_recommended",
    "description",
    "version",
    "release_date",
    "base_url",
}


def _prepare_model_seed(model_data: dict) -> dict:
    """Normalize DEFAULT_MODELS entries for the SQLAlchemy model."""
    model_copy = {key: value for key, value in model_data.items() if key in _LLM_MODEL_COLUMNS}
    if isinstance(model_copy.get("release_date"), str):
        try:
            model_copy["release_date"] = datetime.fromisoformat(model_copy["release_date"])
        except ValueError:
            model_copy["release_date"] = None
    return model_copy


async def ensure_default_providers(db: AsyncSession) -> None:
    """Insert/update built-in providers without requiring an empty table."""
    changed = False
    for provider_data in DEFAULT_PROVIDERS:
        provider = await db.get(LLMProvider, provider_data["id"])
        if provider is None:
            db.add(LLMProvider(**provider_data))
            changed = True
            continue
        for key, value in provider_data.items():
            if key != "id" and getattr(provider, key, None) != value:
                setattr(provider, key, value)
                changed = True
    if changed:
        await db.commit()


async def ensure_default_models(db: AsyncSession) -> None:
    """Insert/update built-in models so new catalog entries appear in existing databases."""
    changed = False
    legacy_recommendation_overrides = {
        ("minimax", "MiniMax-M2.7"): False,
        ("minimax", "MiniMax-M2"): False,
    }
    for model_data in DEFAULT_MODELS:
        model_copy = _prepare_model_seed(model_data)
        model = await db.get(LLMModel, model_copy["id"])
        if model is None:
            db.add(LLMModel(**model_copy))
            changed = True
            continue
        for key, value in model_copy.items():
            if key != "id" and getattr(model, key, None) != value:
                setattr(model, key, value)
                changed = True
    result = await db.execute(select(LLMModel).where(LLMModel.provider_id == "minimax"))
    for model in result.scalars().all():
        override = legacy_recommendation_overrides.get((model.provider_id, model.model_id))
        if override is not None and model.is_recommended != override:
            model.is_recommended = override
            changed = True
    if changed:
        await db.commit()


async def _execute_config_test(
    provider_id: str, api_key: str, model_id: str, message: str,
    *, category: str = "default", model_type: str | None = None,
    driver_key: str | None = None, base_url: str = "", connection_params: dict | None = None,
) -> dict:
    effective_type = model_type or ("speech" if category == "speech" else "chat")
    return await execute_llm_connection_test(
        provider_id, api_key, model_id, message, model_type=effective_type,
        driver_key=driver_key, base_url=base_url, connection_params=connection_params,
    )


# ============== API端点 ==============

@router.get("/providers", response_model=List[LLMProviderResponse])
async def list_providers(
    db: AsyncSession = Depends(get_db)
):
    """获取大模型提供商列表"""
    await ensure_default_providers(db)
    result = await db.execute(
        select(LLMProvider).where(LLMProvider.is_active == True)
    )
    providers = [
        provider for provider in result.scalars().all()
        if is_product_visible_provider(provider)
    ]
    return [
        LLMProviderResponse(
            id=provider.id,
            name=provider.name,
            name_cn=provider.name_cn or provider.name,
            name_en=provider.name_en or provider.name,
            provider_type=provider.provider_type or "cloud",
            base_url=provider.base_url or "",
            is_active=bool(provider.is_active),
            description=provider.description,
            icon_url=provider.icon_url,
        )
        for provider in providers
    ]


@router.get("/models", response_model=List[LLMModelResponse])
async def list_models(
    provider: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取大模型列表"""
    await ensure_default_models(db)
    responses = await project_legacy_llm_models(db, user_id, provider)
    await maybe_log_shadow_catalog_comparison(db, user_id, responses, logger)
    return responses


@router.get("/configs", response_model=List[LLMConfigResponse])
async def list_configs(
    include_model_center_defaults: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取用户的大模型配置列表"""
    result = await db.execute(
        select(LLMConfig, LLMModel)
        .join(LLMModel, LLMConfig.model_id == LLMModel.id)
        .where(
            and_(
                LLMConfig.user_id == user_id,
                LLMConfig.is_active == True
            )
        )
        .order_by(desc(LLMConfig.is_default), desc(LLMConfig.created_at))
    )
    
    configs = []
    for row in result.all():
        config, model = row
        if not is_product_visible_model(model):
            continue
        # 获取provider名称
        provider_result = await db.execute(
            select(LLMProvider).where(LLMProvider.id == model.provider_id)
        )
        provider = provider_result.scalar_one_or_none()
        if provider is not None and not is_product_visible_provider(provider):
            continue
        
        configs.append(build_llm_config_response(config, model, provider))
    
    if include_model_center_defaults:
        bindings = await binding_page(db, user_id, 1, 100)
        canonical_default = canonical_text_default_config(user_id, bindings["items"])
        if canonical_default is not None:
            configs.insert(0, canonical_default)
    return configs


@router.post("/configs", response_model=LLMConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_config(
    request: LLMConfigCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建大模型配置"""
    result = await db.execute(select(LLMModel).where(LLMModel.id == request.model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模型不存在")
    existing_result = await db.execute(
        select(LLMConfig).where(
            and_(
                LLMConfig.user_id == user_id,
                LLMConfig.model_id == request.model_id,
                LLMConfig.is_active == True,
            )
        ).order_by(desc(LLMConfig.updated_at), desc(LLMConfig.created_at))
    )
    config = existing_result.scalars().first()
    if request.is_default:
        await clear_default_configs_for_model_group(
            db,
            user_id,
            model,
            exclude_config_id=config.id if config else None,
        )
    is_existing = config is not None
    if config is None:
        config = LLMConfig(
            id=str(uuid4()),
            user_id=user_id,
            model_id=request.model_id,
            name=request.name,
        )
        db.add(config)
    apply_create_or_upsert_config(config, request, is_existing=is_existing)
    await db.commit()
    await db.refresh(config)
    provider_result = await db.execute(
        select(LLMProvider).where(LLMProvider.id == model.provider_id)
    )
    provider = provider_result.scalar_one_or_none()
    return build_llm_config_response(config, model, provider)


@router.post("/configs/test", response_model=LLMTestResponse)
async def test_api_connection(
    request: LLMTestRequest,
    db: AsyncSession = Depends(get_db)
):
    """测试API连接（无需保存配置）"""
    if not request.api_key or not request.provider_id or not request.model_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="测试未保存配置时必须提供 api_key、provider_id 和 model_id",
        )

    # 获取模型信息
    result = await db.execute(
        select(LLMModel).where(LLMModel.id == request.model_id)
    )
    model = result.scalar_one_or_none()
    
    if not model:
        # 如果数据库中没有模型，使用请求中的信息
        model_provider_id = request.provider_id
        model_id = request.model_id
    else:
        model_provider_id = model.provider_id
        model_id = model.model_id
    
    category = "speech" if model and model.model_type in ("tts", "audio", "speech") else "default"
    base_url = model.base_url if model and model.base_url else ""
    driver_key = await resolve_published_driver_key(db, model.id if model else None)
    return await _execute_config_test(
        model_provider_id, request.api_key, model_id, request.message,
        category=category, model_type=model.model_type if model else None,
        driver_key=driver_key, base_url=base_url,
    )


@router.post("/configs/{config_id}/test", response_model=LLMTestResponse)
async def test_config(
    config_id: str,
    request: LLMTestRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """测试大模型配置"""
    result = await db.execute(
        select(LLMConfig, LLMModel)
        .join(LLMModel, LLMConfig.model_id == LLMModel.id)
        .where(
            and_(
                LLMConfig.id == config_id,
                LLMConfig.user_id == user_id
            )
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在"
        )
    config, model = row
    # 获取provider信息
    provider_result = await db.execute(
        select(LLMProvider).where(LLMProvider.id == model.provider_id)
    )
    provider = provider_result.scalar_one_or_none()
    provider_id = provider.id if provider else model.provider_id
    if deterministic_provider_fake_enabled():
        test_result = deterministic_config_test_result(model.model_id)
        config.test_status = "success"
        config.test_message = test_result["message"]
        config.tested_at = utc_now()
        await db.commit()
        return test_result

    api_key = config.get_api_key_decrypted()
    if not api_key:
        test_result = {
            "success": False,
            "message": "API Key 为空或无法解密，请重新保存并验证该配置",
            "response": None,
            "response_time_ms": 0,
            "tokens_used": 0,
        }
        config.test_status = "failed"
        config.test_message = test_result["message"]
        config.tested_at = utc_now()
        await db.commit()
        return test_result

    category = "speech" if model.model_type in ("tts", "audio", "speech") else "default"
    extra = config.extra_params if isinstance(config.extra_params, dict) else {}
    configured_base_url = configure_volcano_speech_endpoint(
        extra.get("base_url") or model.base_url or (provider.base_url if provider else None), extra,
    ) if category == "speech" else ""
    driver_key = str(extra.get("driver_key") or "").strip() or await resolve_published_driver_key(db, model.id)
    test_result = await _execute_config_test(
        provider_id, api_key, model.model_id, request.message,
        category=category, model_type=model.model_type, driver_key=driver_key,
        base_url=configured_base_url or model.base_url or (provider.base_url if provider else "") or "",
        connection_params=extra,
    )
    # 更新测试状态
    config.test_status = "success" if test_result["success"] else "failed"
    config.test_message = test_result["message"]
    config.tested_at = utc_now()
    await db.commit()
    return test_result


@router.put("/configs/{config_id}", response_model=LLMConfigResponse)
async def update_config(
    config_id: str,
    request: LLMConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新大模型配置"""
    result = await db.execute(
        select(LLMConfig).where(
            and_(
                LLMConfig.id == config_id,
                LLMConfig.user_id == user_id
            )
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在")
    if request.is_default:
        target_model = await db.get(LLMModel, request.model_id)
        if target_model is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模型不存在")
        await clear_default_configs_for_model_group(db, user_id, target_model, exclude_config_id=config_id)
    apply_config_update(config, request)
    await db.commit()
    await db.refresh(config)
    result = await db.execute(select(LLMModel).where(LLMModel.id == config.model_id))
    model = result.scalar_one()
    provider_result = await db.execute(
        select(LLMProvider).where(LLMProvider.id == model.provider_id)
    )
    provider = provider_result.scalar_one_or_none()
    return build_llm_config_response(config, model, provider)


@router.delete("/configs/{config_id}")
async def delete_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除大模型配置"""
    result = await db.execute(
        select(LLMConfig).where(
            and_(
                LLMConfig.id == config_id,
                LLMConfig.user_id == user_id
            )
        )
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在"
        )
    
    config.is_active = False
    await db.commit()
    
    return {"message": "配置已删除"}


@router.post("/configs/{config_id}/set-default")
async def set_default_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """设为默认配置"""
    result = await db.execute(
        select(LLMConfig, LLMModel)
        .join(LLMModel, LLMConfig.model_id == LLMModel.id)
        .where(
            and_(
                LLMConfig.id == config_id,
                LLMConfig.user_id == user_id
            )
        )
    )
    row = result.first()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在"
        )

    config, model = row
    await clear_default_configs_for_model_group(db, user_id, model, exclude_config_id=config_id)
    
    config.is_default = True
    await db.commit()

    return {"message": f"已设为{legacy_model_capability_group(model)}能力默认配置"}


@router.get("/api-key/{provider}", response_model=dict)
async def get_api_key_by_provider(
    provider: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    获取用户是否已配置指定 Provider。

    用于前端页面（如视频生成）判断是否可以使用后端保存的默认配置。
    出于安全考虑，此接口不返回解密后的 API Key。
    支持的 provider: volcano, qianlian, minimax, dashscope, openai
    """
    from app.core.api_key_utils import get_user_api_key
    from app.core.dev_generation import is_dev_mode

    api_key, base_url = await get_user_api_key(
        db, user_id, provider, raise_if_missing=False
    )
    if not api_key:
        return {"api_key": None, "base_url": None, "configured": False, "dev_mode": is_dev_mode()}
    return {"api_key": None, "base_url": base_url, "configured": True, "dev_mode": is_dev_mode()}
