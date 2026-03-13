"""
API密钥管理 API 端点
"""

from typing import Optional, List, Dict
from fastapi import APIRouter, HTTPException, Depends, Form
from pydantic import BaseModel, Field

from app.services.api_key_service import api_key_service

router = APIRouter(prefix="/api/v1/api-keys", tags=["api-keys"])


class APIKeyCreateRequest(BaseModel):
    """创建API密钥请求"""
    provider_id: str = Field(..., description="提供商ID")
    name: Optional[str] = Field(None, description="密钥名称")
    api_key: str = Field(..., description="API Key")
    secret_key: Optional[str] = Field(None, description="Secret Key (部分提供商需要)")
    server_id: Optional[str] = Field(None, description="Server ID (Midjourney需要)")
    channel_id: Optional[str] = Field(None, description="Channel ID (Midjourney需要)")


class APIKeyResponse(BaseModel):
    """API密钥响应"""
    id: str
    provider_id: str
    provider_name: str
    name: str
    masked_credentials: Dict
    is_active: bool
    is_default: bool
    models: List[str]
    created_at: str


@router.get("/providers")
async def get_providers():
    """获取支持的API提供商列表"""
    return {
        "items": api_key_service.get_providers(),
        "total": len(api_key_service.get_providers()),
    }


@router.get("/providers/{provider_id}")
async def get_provider_detail(provider_id: str):
    """获取提供商详情"""
    provider = api_key_service.get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="提供商不存在")
    return provider


@router.get("")
async def list_api_keys():
    """获取当前用户的所有API密钥"""
    # TODO: 从认证获取真实user_id
    user_id = "current_user"
    keys = api_key_service.get_user_api_keys(user_id)
    return {
        "items": keys,
        "total": len(keys),
    }


@router.post("")
async def create_api_key(request: APIKeyCreateRequest):
    """创建新的API密钥配置"""
    user_id = "current_user"
    
    # 构建凭据字典
    credentials = {"api_key": request.api_key}
    if request.secret_key:
        credentials["secret_key"] = request.secret_key
    if request.server_id:
        credentials["server_id"] = request.server_id
    if request.channel_id:
        credentials["channel_id"] = request.channel_id
    
    try:
        key = api_key_service.save_api_key(
            user_id=user_id,
            provider_id=request.provider_id,
            credentials=credentials,
            name=request.name,
        )
        return {
            "success": True,
            "data": key,
            "message": "API密钥配置成功",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{key_id}")
async def delete_api_key(key_id: str):
    """删除API密钥"""
    user_id = "current_user"
    success = api_key_service.delete_api_key(user_id, key_id)
    if not success:
        raise HTTPException(status_code=404, detail="密钥不存在")
    return {"success": True, "message": "密钥已删除"}


@router.post("/{key_id}/default")
async def set_default_key(key_id: str):
    """设置默认API密钥"""
    user_id = "current_user"
    success = api_key_service.set_default_key(user_id, key_id)
    return {"success": success, "message": "默认密钥已设置"}


@router.post("/{key_id}/toggle")
async def toggle_key_active(key_id: str, active: bool = Form(...)):
    """启用/禁用API密钥"""
    user_id = "current_user"
    success = api_key_service.toggle_key_active(user_id, key_id, active)
    if not success:
        raise HTTPException(status_code=404, detail="密钥不存在")
    return {"success": True, "is_active": active}


@router.get("/available-models")
async def get_available_models():
    """获取当前用户可用的模型列表"""
    user_id = "current_user"
    models = api_key_service.get_available_models(user_id)
    return {
        "models": models,
        "summary": {
            "text_generation": len(models.get("text_generation", [])),
            "image_generation": len(models.get("image_generation", [])),
            "video_generation": len(models.get("video_generation", [])),
            "voice_synthesis": len(models.get("voice_synthesis", [])),
            "music_generation": len(models.get("music_generation", [])),
        }
    }


@router.post("/test-connection")
async def test_api_connection(
    provider_id: str = Form(...),
    api_key: str = Form(...),
):
    """测试API连接"""
    # TODO: 实现真实的连接测试
    # 这里返回模拟结果
    return {
        "success": True,
        "provider": provider_id,
        "latency_ms": 120,
        "message": "连接成功（模拟）",
    }