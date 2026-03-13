"""
语音合成 API 端点
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel, Field
import os
import uuid

from app.services.tts_service import tts_service, TTSService

router = APIRouter(prefix="/api/v1/tts", tags=["tts"])


class TTSRequest(BaseModel):
    """语音合成请求"""
    text: str = Field(..., description="要转换的文本", min_length=1, max_length=5000)
    voice: str = Field(default="zh-CN-XiaoxiaoNeural", description="语音选择")
    speed: float = Field(default=1.0, description="语速 0.5-2.0", ge=0.5, le=2.0)
    pitch: str = Field(default="0Hz", description="音调调整")
    volume: str = Field(default="0%", description="音量调整")


class TTSBatchRequest(BaseModel):
    """批量语音合成请求"""
    texts: List[str] = Field(..., description="文本列表", min_items=1, max_items=10)
    voice: str = Field(default="zh-CN-XiaoxiaoNeural", description="语音选择")
    speed: float = Field(default=1.0, description="语速 0.5-2.0")


class TTSResponse(BaseModel):
    """语音合成响应"""
    success: bool
    audio_url: str
    file_size: int
    voice: str
    voice_name: str
    duration: float
    text_length: int


@router.get("/voices", response_model=List[dict])
async def get_voices():
    """获取可用语音列表"""
    return tts_service.get_voice_list()


@router.post("/generate", response_model=TTSResponse)
async def generate_speech(request: TTSRequest):
    """
    生成语音

    将文本转换为语音
    """
    try:
        result = await tts_service.generate_speech(
            text=request.text,
            voice=request.voice,
            speed=request.speed,
            pitch=request.pitch,
            volume=request.volume
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch", response_model=List[TTSResponse])
async def batch_generate_speech(request: TTSBatchRequest):
    """
    批量生成语音

    一次性生成多条语音
    """
    try:
        results = await tts_service.batch_generate(
            texts=request.texts,
            voice=request.voice,
            speed=request.speed
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def tts_health():
    """健康检查"""
    return {"status": "ok", "service": "tts"}


# 静态文件服务配置
# 在 main.py 中添加静态文件服务
# from fastapi.staticfiles import StaticFiles
# app.mount("/storage/tts", StaticFiles(directory="storage/tts"), name="tts")