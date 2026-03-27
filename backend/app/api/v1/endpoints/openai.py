"""
OpenAI API 端点
支持 GPT-4o, GPT-4o-mini, DALL-E, Sora 等模型的调用
"""

import json
from uuid import uuid4
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.services.openai_service import OpenAIService


router = APIRouter(tags=["OpenAI"])


# ============== 数据模型 ==============

class ChatMessage(BaseModel):
    """聊天消息"""
    role: str = Field(..., description="角色: system, user, assistant")
    content: str = Field(..., description="消息内容")


class ChatCompletionRequest(BaseModel):
    """聊天补全请求"""
    model: str = Field("gpt-4o-mini", description="模型ID: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo")
    messages: List[ChatMessage] = Field(..., description="消息列表")
    temperature: float = Field(0.7, ge=0, le=2, description="温度参数")
    max_tokens: Optional[int] = Field(None, ge=1, le=32768, description="最大token数")
    stream: bool = Field(False, description="是否流式输出")


class ChatCompletionResponse(BaseModel):
    """聊天补全响应"""
    id: str
    model: str
    choices: List[dict]
    usage: dict
    created: int
    status: str
    message: str


class ImageGenerateRequest(BaseModel):
    """图像生成请求"""
    prompt: str = Field(..., min_length=1, description="图片描述")
    model: str = Field("dall-e-3", description="模型: dall-e-3, dall-e-2")
    size: str = Field("1024x1024", description="尺寸: 1024x1024, 1024x1792, 1792x1024")
    quality: str = Field("standard", description="质量: standard, hd")
    n: int = Field(1, ge=1, le=4, description="生成数量")
    shot_id: Optional[str] = Field(None, description="关联的镜头ID")


class ImageGenerateResponse(BaseModel):
    """图像生成响应"""
    task_id: str
    image_urls: List[str]
    local_urls: List[str]
    model: str
    status: str
    message: str


class CharacterExtractRequest(BaseModel):
    """AI提取角色请求"""
    text: str = Field(..., min_length=10, description="待分析文本")
    model: str = Field("gpt-4o", description="模型ID: gpt-4o, gpt-4o-mini")
    character_count: int = Field(default=5, ge=1, le=20, description="提取角色数量")


class CharacterExtractResponse(BaseModel):
    """角色提取响应"""
    characters: List[dict]
    status: str
    message: str


class ModelInfo(BaseModel):
    """模型信息"""
    id: str
    name: str
    name_cn: str
    type: str
    capabilities: List[str]
    description: str
    is_recommended: bool


# ============== 辅助函数 ==============

async def get_user_openai_config(db: AsyncSession, user_id: str) -> tuple[str, str]:
    """
    获取用户配置的 OpenAI API 密钥

    Returns:
        tuple: (api_key, model_id)
    """
    # 优先查找默认的 OpenAI 配置
    result = await db.execute(
        select(LLMConfig, LLMModel, LLMProvider)
        .join(LLMModel, LLMConfig.model_id == LLMModel.id)
        .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
        .where(
            and_(
                LLMConfig.user_id == user_id,
                LLMConfig.is_active == True,
                LLMProvider.name == "openai",
            )
        )
        .order_by(desc(LLMConfig.is_default), desc(LLMConfig.last_used_at))
        .limit(1)
    )
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "未找到 OpenAI API Key 配置。"
                "请前往【LLM 配置】页面添加 OpenAI 的 API Key 后重试。"
            ),
        )

    config, model, provider = row
    api_key = config.get_api_key_decrypted()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenAI API 密钥未设置"
        )

    return api_key, model.model_id


async def get_user_openai_api_key(db: AsyncSession, user_id: str) -> str:
    """获取用户配置的 OpenAI API 密钥（解密后）"""
    api_key, _ = await get_user_openai_config(db, user_id)
    return api_key


# ============== API端点 ==============

@router.post("/chat", response_model=ChatCompletionResponse)
async def chat_completion(
    request: ChatCompletionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    OpenAI 聊天补全

    支持模型: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo
    """
    try:
        api_key = await get_user_openai_api_key(db, user_id)
        service = OpenAIService(api_key)

        # 转换消息格式
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]

        result = await service.chat_completion(
            model=request.model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=request.stream
        )

        return ChatCompletionResponse(
            id=result.get("id", str(uuid4())),
            model=result.get("model", request.model),
            choices=result.get("choices", []),
            usage=result.get("usage", {}),
            created=result.get("created", 0),
            status="succeeded",
            message="聊天补全成功"
        )

    except HTTPException:
        raise
    except NotImplementedError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"聊天补全失败: {str(e)}"
        )


@router.post("/image", response_model=ImageGenerateResponse)
async def generate_image(
    request: ImageGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    OpenAI DALL-E 图像生成

    支持模型: dall-e-3 (推荐), dall-e-2
    支持尺寸: 1024x1024, 1024x1792, 1792x1024
    """
    try:
        api_key = await get_user_openai_api_key(db, user_id)
        service = OpenAIService(api_key)

        result = await service.generate_image(
            prompt=request.prompt,
            model=request.model,
            size=request.size,
            quality=request.quality,
            n=request.n,
            save_local=True
        )

        # 提取图片URL
        images = result.get("images", [])
        image_urls = [img.get("url", "") for img in images if isinstance(img, dict)]
        local_urls = result.get("local_urls", [])

        if not image_urls and not local_urls:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="图像生成失败: 未获取到图片URL"
            )

        return ImageGenerateResponse(
            task_id=result.get("task_id", str(uuid4())),
            image_urls=image_urls,
            local_urls=local_urls,
            model=result.get("model", request.model),
            status="succeeded",
            message=f"成功生成 {len(image_urls)} 张图片"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"图像生成失败: {str(e)}"
        )


@router.post("/extract", response_model=CharacterExtractResponse)
async def extract_characters(
    request: CharacterExtractRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    使用 GPT-4o 从文本中提取角色信息
    """
    try:
        api_key = await get_user_openai_api_key(db, user_id)
        service = OpenAIService(api_key)

        result = await service.extract_characters(
            text=request.text,
            model=request.model,
            character_count=request.character_count
        )

        content = result["choices"][0]["message"]["content"]

        # 解析JSON
        json_str = content.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.startswith("```"):
            json_str = json_str[3:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]
        json_str = json_str.strip()

        characters_data = json.loads(json_str)
        if not isinstance(characters_data, list):
            characters_data = [characters_data]
        characters_data = characters_data[:request.character_count]

        return CharacterExtractResponse(
            characters=characters_data,
            status="succeeded",
            message=f"成功提取 {len(characters_data)} 个角色"
        )

    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI返回内容解析失败: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"角色提取失败: {str(e)}"
        )


@router.get("/models", response_model=List[ModelInfo])
async def list_openai_models():
    """
    获取 OpenAI 支持的模型列表

    返回所有 OpenAI 模型的信息，包括文本、图像、视频模型
    """
    from app.core.openai_config import OPENAI_MODELS

    models = []
    for m in OPENAI_MODELS:
        models.append(ModelInfo(
            id=m["id"],
            name=m["name"],
            name_cn=m.get("name_cn", m["name"]),
            type=m["type"],
            capabilities=m.get("capabilities", []),
            description=m.get("description", ""),
            is_recommended=m.get("is_recommended", False)
        ))

    return models
