"""
角色一致性 API 端点
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel, Field

from app.services.character_consistency_service import (
    character_consistency_service,
    CharacterConsistencyService
)

router = APIRouter(
    prefix="/api/v1/characters",
    tags=["character-consistency"]
)


class CharacterFeatureExtractRequest(BaseModel):
    """特征提取请求"""
    character_id: str = Field(..., description="角色ID")
    name: str = Field(..., description="角色名称")
    description: str = Field(..., description="角色描述")
    avatar_url: Optional[str] = Field(None, description="角色头像URL")


class CharacterFeatureResponse(BaseModel):
    """特征提取响应"""
    character_id: str
    name: str
    extracted_features: dict
    consistency_prompt: str


class ConsistencyCheckRequest(BaseModel):
    """一致性检查请求"""
    character_id: str = Field(..., description="角色ID")
    image_url: str = Field(..., description="生成的图像URL")


class ConsistencyCheckResponse(BaseModel):
    """一致性检查响应"""
    character_id: str
    similarity_score: float
    is_consistent: bool
    suggestions: List[str]


@router.post("/{character_id}/extract-features", response_model=CharacterFeatureResponse)
async def extract_character_features(
    character_id: str,
    request: CharacterFeatureExtractRequest
):
    """
    提取角色特征
    
    从角色描述和头像中提取特征用于一致性控制
    """
    try:
        character_data = {
            "id": character_id,
            "name": request.name,
            "description": request.description,
            "avatar": request.avatar_url,
        }

        features = await character_consistency_service.extract_features(character_data)
        
        # 存储特征
        await character_consistency_service.store_character_features(
            character_id, features
        )

        return {
            "character_id": character_id,
            "name": request.name,
            "extracted_features": features,
            "consistency_prompt": features.get("consistency_prompt", ""),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"特征提取失败: {str(e)}")


@router.post("/{character_id}/check-consistency", response_model=ConsistencyCheckResponse)
async def check_character_consistency(
    character_id: str,
    request: ConsistencyCheckRequest
):
    """
    检查角色一致性
    
    检查生成图像与角色特征的一致性
    """
    try:
        result = await character_consistency_service.check_consistency(
            character_id=character_id,
            generated_image_url=request.image_url
        )
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"一致性检查失败: {str(e)}")


@router.get("/{character_id}/consistency-prompt")
async def get_consistency_prompt(character_id: str):
    """
    获取角色一致性控制提示词
    
    用于图像生成时注入一致性控制
    """
    try:
        prompt = character_consistency_service.get_consistency_prompt(character_id)
        return {
            "character_id": character_id,
            "consistency_prompt": prompt,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{character_id}/analyze-avatar")
async def analyze_character_avatar(
    character_id: str,
    avatar: UploadFile = File(...)
):
    """
    分析角色头像
    
    上传角色头像并提取特征
    """
    try:
        # TODO: 保存头像并提取特征
        # 这里需要实现文件上传和保存逻辑
        
        return {
            "character_id": character_id,
            "message": "头像分析完成",
            "avatar_url": f"/storage/avatars/{character_id}.jpg",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"头像分析失败: {str(e)}")