"""
阿里千问（Qwen）API端点
支持对话、小说生成、分镜生成等功能
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.services.dashscope_service import DashScopeService, create_dashscope_service
from app.core.qwen_config import QWEN_MODELS, get_qwen_model

router = APIRouter(tags=["阿里千问"])


# ============== 请求/响应模型 ==============

class ChatRequest(BaseModel):
    """聊天请求"""
    model: str = Field("qwen-plus", description="模型ID")
    messages: List[dict] = Field(..., description="对话消息列表")
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(None, ge=1, le=8192)
    stream: bool = Field(False, description="是否流式输出")
    api_key: str = Field(..., description="DashScope API Key")


class ChatResponse(BaseModel):
    """聊天响应"""
    content: str
    model: str
    usage: dict
    cost: float


class NovelGenerateRequest(BaseModel):
    """小说生成请求"""
    prompt: str = Field(..., description="小说创作提示词")
    model: str = Field("qwen-long", description="模型ID，推荐使用qwen-long")
    max_tokens: int = Field(8000, ge=1000, le=8000)
    temperature: float = Field(0.8, ge=0, le=2)
    api_key: str = Field(..., description="DashScope API Key")


class StoryboardGenerateRequest(BaseModel):
    """分镜生成请求"""
    scene_description: str = Field(..., description="场景描述")
    model: str = Field("qwen-vl-plus", description="模型ID，推荐使用qwen-vl-plus")
    image_url: Optional[str] = Field(None, description="参考图片URL（可选）")
    api_key: str = Field(..., description="DashScope API Key")


class DialogueUnderstandRequest(BaseModel):
    """对话理解请求"""
    user_input: str = Field(..., description="用户输入")
    context: Optional[List[dict]] = Field(None, description="上下文消息")
    model: str = Field("qwen-plus", description="模型ID")
    api_key: str = Field(..., description="DashScope API Key")


class ModelInfoResponse(BaseModel):
    """模型信息响应"""
    id: str
    name: str
    name_cn: str
    type: str
    capabilities: List[str]
    context_window: int
    max_tokens: int
    input_cost_per_1k: float
    output_cost_per_1k: float
    description: str
    use_case: str


# ============== API端点 ==============

@router.get("/models", response_model=List[ModelInfoResponse])
async def list_models():
    """获取阿里千问模型列表"""
    return QWEN_MODELS


@router.get("/models/{model_id}", response_model=ModelInfoResponse)
async def get_model(model_id: str):
    """获取指定模型信息"""
    model = get_qwen_model(model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模型不存在"
        )
    return model


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    通用对话接口
    
    支持所有千问模型，兼容OpenAI API格式
    """
    try:
        service = await create_dashscope_service(request.api_key)
        
        response = await service.chat_completion(
            model=request.model,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=request.stream
        )
        
        # 提取响应内容
        content = response["choices"][0]["message"]["content"]
        usage = response.get("usage", {})
        
        # 计算成本
        cost = service.calculate_request_cost(
            request.model,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0)
        )
        
        return ChatResponse(
            content=content,
            model=request.model,
            usage=usage,
            cost=cost
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"API调用失败: {str(e)}"
        )


@router.post("/generate/novel", response_model=ChatResponse)
async def generate_novel(request: NovelGenerateRequest):
    """
    生成小说
    
    使用 qwen-long 模型，支持长文本生成
    """
    try:
        service = await create_dashscope_service(request.api_key)
        
        response = await service.generate_novel(
            prompt=request.prompt,
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )
        
        content = response["choices"][0]["message"]["content"]
        usage = response.get("usage", {})
        
        cost = service.calculate_request_cost(
            request.model,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0)
        )
        
        return ChatResponse(
            content=content,
            model=request.model,
            usage=usage,
            cost=cost
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"小说生成失败: {str(e)}"
        )


@router.post("/generate/storyboard", response_model=ChatResponse)
async def generate_storyboard(request: StoryboardGenerateRequest):
    """
    生成视频分镜
    
    使用 qwen-vl-plus 视觉模型，结合图像理解生成分镜
    """
    try:
        service = await create_dashscope_service(request.api_key)
        
        response = await service.generate_storyboard(
            scene_description=request.scene_description,
            model=request.model,
            image_url=request.image_url
        )
        
        content = response["choices"][0]["message"]["content"]
        usage = response.get("usage", {})
        
        cost = service.calculate_request_cost(
            request.model,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0)
        )
        
        return ChatResponse(
            content=content,
            model=request.model,
            usage=usage,
            cost=cost
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"分镜生成失败: {str(e)}"
        )


@router.post("/understand/dialogue", response_model=ChatResponse)
async def understand_dialogue(request: DialogueUnderstandRequest):
    """
    对话理解
    
    理解用户需求，提取关键信息
    """
    try:
        service = await create_dashscope_service(request.api_key)
        
        response = await service.understand_dialogue(
            user_input=request.user_input,
            context=request.context,
            model=request.model
        )
        
        content = response["choices"][0]["message"]["content"]
        usage = response.get("usage", {})
        
        cost = service.calculate_request_cost(
            request.model,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0)
        )
        
        return ChatResponse(
            content=content,
            model=request.model,
            usage=usage,
            cost=cost
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"对话理解失败: {str(e)}"
        )


@router.post("/test")
async def test_connection(api_key: str):
    """
    测试API连接
    
    验证API Key是否有效
    """
    try:
        service = await create_dashscope_service(api_key)
        
        # 简单测试调用
        response = await service.chat_completion(
            model="qwen-turbo",
            messages=[{"role": "user", "content": "你好"}],
            max_tokens=10
        )
        
        return {

            "success": True,
            "message": "连接成功",
            "model": "qwen-turbo"
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"连接失败: {str(e)}"
        }
