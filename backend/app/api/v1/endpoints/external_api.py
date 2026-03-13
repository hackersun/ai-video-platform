"""
外部API配置与管理
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

from app.services.external_api_service import APIAdapterFactory

router = APIRouter(prefix="/api/v1/external", tags=["external-api"])


class APIConfigResponse(BaseModel):
    """API配置响应"""
    provider: str
    name: str
    type: str
    is_configured: bool
    api_key_env: str
    base_url: Optional[str] = None
    status: str


class GenerateRequest(BaseModel):
    """生成请求"""
    provider: str = Field(..., description="提供商")
    task_type: str = Field(..., description="任务类型")
    params: dict = Field(default_factory=dict)


class GenerateResponse(BaseModel):
    """生成响应"""
    success: bool
    task_id: str
    status: str
    message: str
    result: Optional[dict] = None


@router.get("/providers")
async def get_providers():
    """获取支持的外部API提供商"""
    providers = APIAdapterFactory.get_all_providers()
    
    # 检查每个提供商的配置状态
    result = []
    for p in providers:
        is_configured = bool(
            p["id"].upper() + "_API_KEY" in __import__("os").environ
        )
        result.append({
            **p,
            "is_configured": is_configured,
            "status": "active" if is_configured else "not_configured",
        })
    
    return {"items": result, "total": len(result)}


@router.get("/config")
async def get_api_configs():
    """获取API配置列表"""
    providers = APIAdapterFactory.get_all_providers()
    
    configs = []
    for p in providers:
        provider_id = p["id"]
        env_key = f"{provider_id.upper()}_API_KEY"
        is_configured = env_key in __import__("os").environ
        
        configs.append({
            "provider": provider_id,
            "name": p["name"],
            "type": p["type"],
            "is_configured": is_configured,
            "api_key_env": env_key,
            "base_url": f"https://api.{provider_id}.com/v1" if not is_configured else None,
            "status": "active" if is_configured else "not_configured",
        })
    
    return {"items": configs, "total": len(configs)}


class APIConfigRequest(BaseModel):
    """API配置请求"""
    api_key: str = Field(..., description="API Key")
    base_url: Optional[str] = Field(None, description="自定义API地址")


@router.post("/config/{provider}")
async def configure_api(
    provider: str,
    config: APIConfigRequest,
):
    """配置API密钥"""
    # 注意：实际应用中应该加密存储
    return {
        "provider": provider,
        "message": "API配置已保存（演示模式）",
        "is_configured": True,
        "api_key": config.api_key[:4] + "****",
    }


@router.post("/generate", response_model=GenerateResponse)
async def generate_content(request: GenerateRequest):
    """通用生成接口"""
    try:
        adapter = APIAdapterFactory.get_adapter(request.provider)
        
        # 根据任务类型调用不同的方法
        if request.task_type == "text_to_image":
            result = await adapter.generate(prompt=request.params.get("prompt"))
        elif request.task_type == "image_to_video":
            result = await adapter.generate(
                image_url=request.params.get("image_url"),
                prompt=request.params.get("prompt"),
            )
        elif request.task_type == "text_to_video":
            result = await adapter.generate(prompt=request.params.get("prompt"))
        elif request.task_type == "text_to_speech":
            result = await adapter.text_to_speech(
                text=request.params.get("text"),
                voice_id=request.params.get("voice_id", "pNInz6obpgDQGcFmaJgB"),
            )
        elif request.task_type == "music_generation":
            result = await adapter.generate(
                prompt=request.params.get("prompt"),
                lyrics=request.params.get("lyrics"),
            )
        else:
            raise HTTPException(status_code=400, detail=f"不支持的任务类型: {request.task_type}")
        
        return {
            "success": True,
            "task_id": result.get("task_id", ""),
            "status": result.get("status", "processing"),
            "message": "生成任务已提交",
            "result": result,
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@router.get("/task/{task_id}")
async def get_task_status(
    task_id: str,
    provider: str = Query(..., description="提供商"),
):
    """获取任务状态"""
    try:
        adapter = APIAdapterFactory.get_adapter(provider)
        status = await adapter.get_task_status(task_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== 各提供商专用接口 ==========

@router.post("/midjourney/imagine")
async def midjourney_imagine(
    prompt: str,
    negative_prompt: str = "",
    aspect_ratio: str = "1:1",
    stylize: int = 100,
):
    """Midjourney 生成图像"""
    try:
        adapter = APIAdapterFactory.get_adapter("midjourney")
        result = await adapter.generate(
            prompt=prompt,
            negative_prompt=negative_prompt,
            aspect_ratio=aspect_ratio,
            stylize=stylize,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/runway/generate")
async def runway_generate(
    prompt: str = None,
    image_url: str = None,
    duration: int = 5,
    model: str = "gen3_alpha_turbo",
):
    """Runway 生成视频"""
    try:
        adapter = APIAdapterFactory.get_adapter("runway")
        result = await adapter.generate(
            prompt=prompt,
            image_url=image_url,
            duration=duration,
            model=model,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pika/generate")
async def pika_generate(
    prompt: str = None,
    image_url: str = None,
    aspect_ratio: str = "16:9",
    motion_strength: int = 5,
):
    """Pika 生成视频"""
    try:
        adapter = APIAdapterFactory.get_adapter("pika")
        result = await adapter.generate(
            prompt=prompt,
            image_url=image_url,
            aspect_ratio=aspect_ratio,
            motion_strength=motion_strength,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suno/generate")
async def suno_generate(
    prompt: str = None,
    lyrics: str = None,
    title: str = None,
    make_instrumental: bool = False,
):
    """Suno 生成音乐"""
    try:
        adapter = APIAdapterFactory.get_adapter("suno")
        result = await adapter.generate(
            prompt=prompt,
            lyrics=lyrics,
            title=title,
            make_instrumental=make_instrumental,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/elevenlabs/tts")
async def elevenlabs_tts(
    text: str,
    voice_id: str = "pNInz6obpgDQGcFmaJgB",
    model_id: str = "eleven_multilingual_v2",
    stability: float = 0.5,
    similarity_boost: float = 0.75,
):
    """ElevenLabs 语音合成"""
    try:
        adapter = APIAdapterFactory.get_adapter("elevenlabs")
        result = await adapter.text_to_speech(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            stability=stability,
            similarity_boost=similarity_boost,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))