"""
大模型配置API
支持多模型接入配置管理
"""

from typing import List, Optional
from datetime import datetime
from uuid import uuid4
import httpx
import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.llm_config import LLMProvider, LLMModel, LLMConfig, LLMUsageLog

router = APIRouter(tags=["大模型配置"])


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


class LLMConfigResponse(BaseModel):
    """配置响应"""
    id: str
    user_id: str
    model_id: str
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
    usage_count: int
    created_at: datetime
    updated_at: datetime


class LLMTestRequest(BaseModel):
    """测试请求"""
    api_key: str = Field(..., description="API密钥")
    provider_id: str = Field(..., description="提供商ID")
    model_id: str = Field(..., description="模型ID")
    message: str = Field("你好，请介绍一下自己", description="测试消息")


class LLMTestResponse(BaseModel):
    """测试响应"""
    success: bool
    message: str
    response: Optional[str]
    response_time_ms: Optional[int]
    tokens_used: Optional[int]


# ============== 预设数据 ==============

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
    }
]

DEFAULT_MODELS = [
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
    {
        "id": "doubao-seedream-4.5",
        "provider_id": "volcano",
        "model_id": "Doubao-Seedream-4.5",
        "model_name": "Doubao-Seedream-4.5",
        "model_name_cn": "豆包Seedream-4.5",
        "model_type": "image-generation",
        "capabilities": ["text-to-image", "image-edit", "inpainting", "outpainting"],
        "context_window": 4096,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.05,
        "output_cost_per_1k": 0.05,
        "supports_streaming": False,
        "supports_function_calling": False,
        "supports_vision": False,
        "supports_json_mode": False,
        "is_active": True,
        "is_recommended": True,
        "description": "火山引擎高质量图像生成模型，支持文生图、图像编辑等",
        "version": "4.5",
        "release_date": "2026-03-01",
        "endpoint_id": "ep-20260320112226-rgndq"
    },
    {
        "id": "doubao-seedream-5.0-lite",
        "provider_id": "volcano",
        "model_id": "Doubao-Seedream-5.0-lite",
        "model_name": "Doubao-Seedream-5.0-lite",
        "model_name_cn": "豆包Seedream-5.0-lite",
        "model_type": "image-generation",
        "capabilities": ["text-to-image", "image-edit", "inpainting"],
        "context_window": 4096,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.02,
        "output_cost_per_1k": 0.02,
        "supports_streaming": False,
        "supports_function_calling": False,
        "supports_vision": False,
        "supports_json_mode": False,
        "is_active": True,
        "is_recommended": True,
        "description": "豆包轻量级图像生成模型，性价比高",
        "version": "5.0-lite",
        "release_date": "2026-03-01",
        "endpoint_id": "ep-20260320113731-jzjkn"
    },
    {
        "id": "doubao-seed-2.0-pro",
        "provider_id": "volcano",
        "model_id": "Doubao-Seed-2.0-pro",
        "model_name": "Doubao-Seed-2.0-pro",
        "model_name_cn": "豆包Seed-2.0-pro",
        "model_type": "video-generation",
        "capabilities": ["text-to-video", "image-to-video", "video-edit"],
        "context_window": 4096,
        "max_tokens": 4096,
        "input_cost_per_1k": 0.5,
        "output_cost_per_1k": 0.5,
        "supports_streaming": False,
        "supports_function_calling": False,
        "supports_vision": False,
        "supports_json_mode": False,
        "is_active": True,
        "is_recommended": True,
        "description": "火山引擎高质量视频生成模型，支持文生视频、图生视频",
        "version": "2.0-pro",
        "release_date": "2026-03-01",
        "endpoint_id": "ep-20260320111926-sn9tg"
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
    }
]


# ============== 辅助函数 ==============

async def test_volcano_api(api_key: str, model_id: str, message: str) -> dict:
    """测试火山引擎API，根据模型类型走不同端点"""
    from app.core.volcano_config import VOLCANO_MODELS

    # 查找模型类型
    model_type = "text-generation"  # 默认为文本模型
    for m in VOLCANO_MODELS:
        if m["id"] == model_id:
            model_type = m.get("type", "text-generation")
            break

    base_url = "https://ark.cn-beijing.volces.com/api/v3"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    if model_type == "video-generation":
        # 视频生成模型 → POST /contents/generations/tasks
        url = f"{base_url}/contents/generations/tasks"
        data = {
            "model": model_id,
            "content": [
                {"type": "text", "text": f"{message} --duration 4 --resolution 720p --camerafixed true --watermark true"}
            ]
        }
    elif model_type == "image-generation":
        # 图像生成模型 → POST /images/generations
        url = f"{base_url}/images/generations"
        data = {
            "model": model_id,
            "prompt": message[:200],
            "size": "1024x1024",
            "n": 1,
            "response_format": "url"
        }
    else:
        # 文本生成模型 → POST /chat/completions
        url = f"{base_url}/chat/completions"
        data = {
            "model": model_id,
            "messages": [{"role": "user", "content": message}],
            "max_tokens": 100
        }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=data, headers=headers)

            if response.status_code == 200:
                result = response.json()
                if model_type == "video-generation":
                    task_id = result.get("id", "unknown")
                    return {
                        "success": True,
                        "message": f"火山引擎视频模型 API 连接成功！任务ID: {task_id}",
                        "response": f"任务已提交: {task_id}",
                        "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                        "tokens_used": 0
                    }
                elif model_type == "image-generation":
                    return {
                        "success": True,
                        "message": "火山引擎图像模型 API 连接成功！",
                        "response": result.get("data", [{}])[0].get("url", "响应成功"),
                        "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                        "tokens_used": 0
                    }
                else:
                    return {
                        "success": True,
                        "message": "火山引擎 API 连接成功！",
                        "response": result.get("choices", [{}])[0].get("message", {}).get("content", "响应成功"),
                        "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                        "tokens_used": result.get("usage", {}).get("total_tokens", 0)
                    }
            else:
                try:
                    err_json = response.json()
                    err_msg = err_json.get("error", {}).get("message", err_json.get("message", response.text[:200]))
                except Exception:
                    err_msg = response.text[:200]
                return {
                    "success": False,
                    "message": f"[HTTP {response.status_code}] API错误: {err_msg}\n模型ID: {model_id} | 端点: {url}",
                    "response": None,
                    "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                    "tokens_used": 0
                }
    except httpx.TimeoutException:
        return {
            "success": False,
            "message": f"连接超时(30s)，请检查网络或API地址是否正确\n请求地址: {url}",
            "response": None,
            "response_time_ms": 30000,
            "tokens_used": 0
        }
    except httpx.ConnectError as e:
        return {
            "success": False,
            "message": f"连接失败，无法访问API地址: {e}\n请求地址: {url}",
            "response": None,
            "response_time_ms": 0,
            "tokens_used": 0
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"测试异常: {str(e)[:300]}",
            "response": None,
            "response_time_ms": 0,
            "tokens_used": 0
        }


async def test_qwen_api(api_key: str, model_id: str, message: str) -> dict:
    """测试阿里千问API"""
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data = {
        "model": model_id,
        "input": {"messages": [{"role": "user", "content": message}]},
        "parameters": {"max_tokens": 100}
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=data, headers=headers)

            if response.status_code == 200:
                result = response.json()
                content = result.get("output", {}).get("text") or result.get("choices", [{}])[0].get("message", {}).get("content", "响应成功")
                return {
                    "success": True,
                    "message": "阿里千问 API 连接成功！",
                    "response": content,
                    "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                    "tokens_used": result.get("usage", {}).get("total_tokens", 0) or result.get("usage", {}).get("input_tokens", 0) + result.get("usage", {}).get("output_tokens", 0)
                }
            else:
                try:
                    err_json = response.json()
                    err_msg = err_json.get("error", {}).get("message", err_json.get("message", response.text[:200]))
                except Exception:
                    err_msg = response.text[:200]
                return {
                    "success": False,
                    "message": f"[HTTP {response.status_code}] API错误: {err_msg}",
                    "response": None,
                    "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                    "tokens_used": 0
                }
    except httpx.TimeoutException:
        return {
            "success": False,
            "message": f"连接超时(30s)，请检查网络或API地址是否正确\n请求地址: {url}",
            "response": None,
            "response_time_ms": 30000,
            "tokens_used": 0
        }
    except httpx.ConnectError as e:
        return {
            "success": False,
            "message": f"连接失败，无法访问API地址: {e}\n请求地址: {url}",
            "response": None,
            "response_time_ms": 0,
            "tokens_used": 0
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"测试异常: {str(e)[:300]}",
            "response": None,
            "response_time_ms": 0,
            "tokens_used": 0
        }


async def test_qianlian_api(api_key: str, model_id: str, message: str) -> dict:
    """测试阿里百炼API (Anthropic 兼容格式)"""
    url = "https://coding.dashscope.aliyuncs.com/apps/anthropic/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "anthropic-version": "2023-06-01"
    }
    data = {
        "model": model_id,
        "messages": [{"role": "user", "content": message}],
        "max_tokens": 100
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=data, headers=headers)

            if response.status_code == 200:
                result = response.json()
                contents = result.get("content", [])
                content = next((c.get("text", "") for c in contents if c.get("type") == "text"), "响应成功")
                return {
                    "success": True,
                    "message": "阿里百炼 API 连接成功！",
                    "response": content[:500] if content else "响应成功",
                    "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                    "tokens_used": result.get("usage", {}).get("output_tokens", 0)
                }
            else:
                try:
                    err_json = response.json()
                    err_type = err_json.get("type", "unknown")
                    err_msg = err_json.get("error", {}).get("message", err_json.get("message", response.text[:200]))
                    error_detail = f"[HTTP {response.status_code}] {err_type}: {err_msg}"
                except Exception:
                    error_detail = f"[HTTP {response.status_code}] {response.text[:200]}"
                return {
                    "success": False,
                    "message": f"API错误: {error_detail}",
                    "response": None,
                    "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                    "tokens_used": 0
                }
    except httpx.TimeoutException:
        return {
            "success": False,
            "message": "连接超时(60s)，请检查网络或API地址是否正确",
            "response": None,
            "response_time_ms": 60000,
            "tokens_used": 0
        }
    except httpx.ConnectError as e:
        return {
            "success": False,
            "message": f"连接失败，无法访问API地址: {e}",
            "response": None,
            "response_time_ms": 0,
            "tokens_used": 0
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"测试异常: {str(e)[:300]}",
            "response": None,
            "response_time_ms": 0,
            "tokens_used": 0
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"连接失败: {str(e)[:100]}",
            "response": None,
            "response_time_ms": 0,
            "tokens_used": 0
        }


async def test_baidu_api(api_key: str, model_id: str, message: str) -> dict:
    """测试百度文心一言API"""
    # 百度千帆平台使用IAM认证或Access Token
    # 兼容模式使用Access Token方式
    url = "https://qianfan.baidubce.com/v2/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data = {
        "model": model_id,
        "messages": [{"role": "user", "content": message}],
        "max_tokens": 100
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=data, headers=headers)

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "message": "百度文心一言 API 连接成功！",
                    "response": result.get("choices", [{}])[0].get("message", {}).get("content", "响应成功"),
                    "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                    "tokens_used": result.get("usage", {}).get("total_tokens", 0)
                }
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("error", {}).get("message", response.text[:100]) if isinstance(error_data, dict) else str(error_data)[:100]
                return {
                    "success": False,
                    "message": f"API错误: {error_msg}",
                    "response": None,
                    "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                    "tokens_used": 0
                }
    except httpx.TimeoutException:
        return {
            "success": False,
            "message": "连接超时，请检查网络或API地址",
            "response": None,
            "response_time_ms": 30000,
            "tokens_used": 0
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"连接失败: {str(e)[:100]}",
            "response": None,
            "response_time_ms": 0,
            "tokens_used": 0
        }


async def test_openai_api(api_key: str, model_id: str, message: str) -> dict:
    """测试 OpenAI API"""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data = {
        "model": model_id,
        "messages": [{"role": "user", "content": message}],
        "max_tokens": 100
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=data, headers=headers)

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "message": "OpenAI API 连接成功！",
                    "response": result.get("choices", [{}])[0].get("message", {}).get("content", "响应成功"),
                    "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                    "tokens_used": result.get("usage", {}).get("total_tokens", 0)
                }
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("error", {}).get("message", response.text[:100]) if isinstance(error_data, dict) else str(response.text)[:100]
                return {
                    "success": False,
                    "message": f"API错误: {error_msg}",
                    "response": None,
                    "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                    "tokens_used": 0
                }
    except httpx.TimeoutException:
        return {
            "success": False,
            "message": "连接超时，请检查网络或API地址",
            "response": None,
            "response_time_ms": 30000,
            "tokens_used": 0
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"连接失败: {str(e)[:100]}",
            "response": None,
            "response_time_ms": 0,
            "tokens_used": 0
        }


# ============== API端点 ==============

@router.get("/providers", response_model=List[LLMProviderResponse])
async def list_providers(
    db: AsyncSession = Depends(get_db)
):
    """获取大模型提供商列表"""
    result = await db.execute(
        select(LLMProvider).where(LLMProvider.is_active == True)
    )
    providers = result.scalars().all()
    
    if not providers:
        # 初始化预设数据
        for provider_data in DEFAULT_PROVIDERS:
            provider = LLMProvider(**provider_data)
            db.add(provider)
        await db.commit()
        
        # 重新查询
        result = await db.execute(
            select(LLMProvider).where(LLMProvider.is_active == True)
        )
        providers = result.scalars().all()
    
    return providers


@router.get("/models", response_model=List[LLMModelResponse])
async def list_models(
    provider: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取大模型列表"""
    from datetime import datetime
    
    query = select(LLMModel).where(LLMModel.is_active == True)
    
    if provider:
        query = query.where(LLMModel.provider_id == provider)
    
    result = await db.execute(query)
    models = result.scalars().all()
    
    if not models:
        # 初始化预设模型
        for model_data in DEFAULT_MODELS:
            # 转换 release_date 字符串为 datetime 对象
            model_copy = model_data.copy()
            if 'release_date' in model_copy and model_copy['release_date']:
                try:
                    model_copy['release_date'] = datetime.fromisoformat(model_copy['release_date'])
                except:
                    model_copy['release_date'] = None
            model = LLMModel(**model_copy)
            db.add(model)
        await db.commit()
        
        # 重新查询
        result = await db.execute(query)
        models = result.scalars().all()
    
    return models


@router.get("/configs", response_model=List[LLMConfigResponse])
async def list_configs(
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
        # 获取provider名称
        provider_result = await db.execute(
            select(LLMProvider).where(LLMProvider.id == model.provider_id)
        )
        provider = provider_result.scalar_one_or_none()
        
        configs.append({
            "id": config.id,
            "user_id": config.user_id,
            "model_id": config.model_id,
            "model_name": model.model_name_cn or model.model_name,
            "provider_name": provider.name_cn if provider else "未知",
            "name": config.name,
            "temperature": config.temperature,
            "top_p": config.top_p,
            "max_tokens": config.max_tokens,
            "is_active": config.is_active,
            "is_default": config.is_default,
            "test_status": config.test_status,
            "test_message": config.test_message,
            "usage_count": config.usage_count,
            "created_at": config.created_at,
            "updated_at": config.updated_at
        })
    
    return configs


@router.post("/configs", response_model=LLMConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_config(
    request: LLMConfigCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建大模型配置"""
    # 验证模型是否存在
    result = await db.execute(
        select(LLMModel).where(LLMModel.id == request.model_id)
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模型不存在"
        )
    
    # 如果设为默认，取消其他默认配置
    if request.is_default:
        await db.execute(
            select(LLMConfig)
            .where(and_(LLMConfig.user_id == user_id, LLMConfig.is_default == True))
            .update({"is_default": False})
        )
    
    # TODO: 加密存储API密钥
    config = LLMConfig(
        id=str(uuid4()),
        user_id=user_id,
        model_id=request.model_id,
        name=request.name,
        api_key=request.api_key,  # 需要加密
        api_secret=request.api_secret,
        temperature=request.temperature,
        top_p=request.top_p,
        max_tokens=request.max_tokens,
        extra_params=request.extra_params,
        is_default=request.is_default,
        test_status="pending"
    )
    
    db.add(config)
    await db.commit()
    await db.refresh(config)
    
    # 获取provider信息
    provider_result = await db.execute(
        select(LLMProvider).where(LLMProvider.id == model.provider_id)
    )
    provider = provider_result.scalar_one_or_none()
    
    return {
        "id": config.id,
        "user_id": config.user_id,
        "model_id": config.model_id,
        "model_name": model.model_name_cn or model.model_name,
        "provider_name": provider.name_cn if provider else "未知",
        "name": config.name,
        "temperature": config.temperature,
        "top_p": config.top_p,
        "max_tokens": config.max_tokens,
        "is_active": config.is_active,
        "is_default": config.is_default,
        "test_status": config.test_status,
        "test_message": config.test_message,
        "usage_count": config.usage_count,
        "created_at": config.created_at,
        "updated_at": config.updated_at
    }


@router.post("/configs/test", response_model=LLMTestResponse)
async def test_api_connection(
    request: LLMTestRequest,
    db: AsyncSession = Depends(get_db)
):
    """测试API连接（无需保存配置）"""
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
    
    # 根据提供商调用不同的测试函数
    if model_provider_id == "volcano":
        return await test_volcano_api(request.api_key, model_id, request.message)
    elif model_provider_id == "qwen":
        return await test_qwen_api(request.api_key, model_id, request.message)
    elif model_provider_id == "qianlian":
        return await test_qianlian_api(request.api_key, model_id, request.message)
    elif model_provider_id == "baidu":
        return await test_baidu_api(request.api_key, model_id, request.message)
    elif model_provider_id == "openai":
        return await test_openai_api(request.api_key, model_id, request.message)
    else:
        return {
            "success": False,
            "message": f"不支持的提供商: {model_provider_id}",
            "response": None,
            "response_time_ms": 0,
            "tokens_used": 0
        }


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
    
    # 根据提供商调用测试
    if provider_id == "volcano":
        test_result = await test_volcano_api(config.api_key, model.model_id, request.message)
    elif provider_id == "qwen":
        test_result = await test_qwen_api(config.api_key, model.model_id, request.message)
    elif provider_id == "qianlian":
        test_result = await test_qianlian_api(config.api_key, model.model_id, request.message)
    elif provider_id == "baidu":
        test_result = await test_baidu_api(config.api_key, model.model_id, request.message)
    elif provider_id == "openai":
        test_result = await test_openai_api(config.api_key, model.model_id, request.message)
    else:
        test_result = {
            "success": False,
            "message": f"不支持的提供商: {provider_id}",
            "response": None,
            "response_time_ms": 0,
            "tokens_used": 0
        }
    
    # 更新测试状态
    config.test_status = "success" if test_result["success"] else "failed"
    config.test_message = test_result["message"]
    config.tested_at = datetime.utcnow()
    await db.commit()
    
    return test_result


@router.put("/configs/{config_id}", response_model=LLMConfigResponse)
async def update_config(
    config_id: str,
    request: LLMConfigCreateRequest,
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在"
        )
    
    # 更新字段
    config.name = request.name
    config.api_key = request.api_key  # 需要加密
    config.api_secret = request.api_secret
    config.temperature = request.temperature
    config.top_p = request.top_p
    config.max_tokens = request.max_tokens
    config.extra_params = request.extra_params
    config.is_default = request.is_default
    config.test_status = "pending"  # 重置测试状态
    
    await db.commit()
    await db.refresh(config)
    
    # 获取模型信息
    result = await db.execute(
        select(LLMModel).where(LLMModel.id == config.model_id)
    )
    model = result.scalar_one()
    
    # 获取provider信息
    provider_result = await db.execute(
        select(LLMProvider).where(LLMProvider.id == model.provider_id)
    )
    provider = provider_result.scalar_one_or_none()
    
    return {
        "id": config.id,
        "user_id": config.user_id,
        "model_id": config.model_id,
        "model_name": model.model_name_cn or model.model_name,
        "provider_name": provider.name_cn if provider else "未知",
        "name": config.name,
        "temperature": config.temperature,
        "top_p": config.top_p,
        "max_tokens": config.max_tokens,
        "is_active": config.is_active,
        "is_default": config.is_default,
        "test_status": config.test_status,
        "test_message": config.test_message,
        "usage_count": config.usage_count,
        "created_at": config.created_at,
        "updated_at": config.updated_at
    }


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
    # 取消其他默认配置
    await db.execute(
        select(LLMConfig)
        .where(and_(LLMConfig.user_id == user_id, LLMConfig.is_default == True))
        .update({"is_default": False})
    )
    
    # 设置新的默认配置
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
    
    config.is_default = True
    await db.commit()
    
    return {"message": "已设为默认配置"}
