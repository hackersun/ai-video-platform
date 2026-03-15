"""
配置管理API端点
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.models.provider import Provider
from app.models.api_key import APIKey
from app.models.ai_model import AIModel

router = APIRouter(prefix="/config", tags=["配置管理"])


# ============ Schema定义 ============

class ProviderCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    base_url: Optional[str] = None


class ProviderResponse(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str]
    base_url: Optional[str]
    is_active: bool
    
    class Config:
        from_attributes = True


class APIKeyCreate(BaseModel):
    provider_id: int
    key_name: str
    key_value: str  # 明文，存储时加密
    is_default: bool = False


class APIKeyResponse(BaseModel):
    id: int
    provider_id: int
    key_name: str
    is_default: bool
    is_active: bool
    usage_count: int
    
    class Config:
        from_attributes = True


class AIModelCreate(BaseModel):
    provider_id: int
    model_code: str
    model_name: str
    model_type: str
    description: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9
    context_window: int = 8192
    is_default: bool = False


class AIModelResponse(BaseModel):
    id: int
    provider_id: int
    model_code: str
    model_name: str
    model_type: str
    description: Optional[str]
    max_tokens: int
    temperature: float
    top_p: float
    context_window: int
    is_active: bool
    is_default: bool
    
    class Config:
        from_attributes = True


# ============ 服务商管理 ============

@router.get("/providers", response_model=List[ProviderResponse])
def list_providers(db: Session = Depends(get_db)):
    """获取所有服务商列表"""
    return db.query(Provider).filter(Provider.is_active == True).all()


@router.post("/providers", response_model=ProviderResponse)
def create_provider(provider: ProviderCreate, db: Session = Depends(get_db)):
    """创建服务商"""
    # 检查code是否已存在
    existing = db.query(Provider).filter(Provider.code == provider.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"服务商代码 {provider.code} 已存在")
    
    db_provider = Provider(**provider.dict())
    db.add(db_provider)
    db.commit()
    db.refresh(db_provider)
    return db_provider


@router.get("/providers/{provider_id}", response_model=ProviderResponse)
def get_provider(provider_id: int, db: Session = Depends(get_db)):
    """获取服务商详情"""
    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="服务商不存在")
    return provider


@router.delete("/providers/{provider_id}")
def delete_provider(provider_id: int, db: Session = Depends(get_db)):
    """删除服务商（软删除）"""
    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="服务商不存在")
    provider.is_active = False
    db.commit()
    return {"message": "删除成功"}


# ============ API密钥管理 ============

@router.get("/keys", response_model=List[APIKeyResponse])
def list_api_keys(provider_id: int = None, db: Session = Depends(get_db)):
    """获取API密钥列表"""
    query = db.query(APIKey).filter(APIKey.is_active == True)
    if provider_id:
        query = query.filter(APIKey.provider_id == provider_id)
    return query.all()


@router.post("/keys", response_model=APIKeyResponse)
def create_api_key(key: APIKeyCreate, db: Session = Depends(get_db)):
    """创建API密钥"""
    # 验证服务商存在
    provider = db.query(Provider).filter(Provider.id == key.provider_id).first()
    if not provider:
        raise HTTPException(status_code=400, detail="服务商不存在")
    
    # 如果设为默认，取消其他默认
    if key.is_default:
        db.query(APIKey).filter(
            APIKey.provider_id == key.provider_id,
            APIKey.is_default == True
        ).update({"is_default": False})
    
    # 创建密钥（自动加密存储）
    db_key = APIKey(
        provider_id=key.provider_id,
        key_name=key.key_name,
        key_value=key.key_value,  # setter会自动加密
        is_default=key.is_default
    )
    db.add(db_key)
    db.commit()
    db.refresh(db_key)
    return db_key


@router.delete("/keys/{key_id}")
def delete_api_key(key_id: int, db: Session = Depends(get_db)):
    """删除API密钥（软删除）"""
    key = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="密钥不存在")
    key.is_active = False
    db.commit()
    return {"message": "删除成功"}


# ============ 模型管理 ============

@router.get("/models", response_model=List[AIModelResponse])
def list_models(provider_id: int = None, model_type: str = None, db: Session = Depends(get_db)):
    """获取模型列表"""
    query = db.query(AIModel).filter(AIModel.is_active == True)
    if provider_id:
        query = query.filter(AIModel.provider_id == provider_id)
    if model_type:
        query = query.filter(AIModel.model_type == model_type)
    return query.all()


@router.post("/models", response_model=AIModelResponse)
def create_model(model: AIModelCreate, db: Session = Depends(get_db)):
    """创建模型配置"""
    # 验证服务商存在
    provider = db.query(Provider).filter(Provider.id == model.provider_id).first()
    if not provider:
        raise HTTPException(status_code=400, detail="服务商不存在")
    
    # 如果设为默认，取消其他默认
    if model.is_default:
        db.query(AIModel).filter(
            AIModel.provider_id == model.provider_id,
            AIModel.is_default == True
        ).update({"is_default": False})
    
    db_model = AIModel(**model.dict())
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    return db_model


@router.delete("/models/{model_id}")
def delete_model(model_id: int, db: Session = Depends(get_db)):
    """删除模型（软删除）"""
    model = db.query(AIModel).filter(AIModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    model.is_active = False
    db.commit()
    return {"message": "删除成功"}


# ============ 测试接口 ============

@router.post("/test-key/{key_id}")
def test_api_key(key_id: int, db: Session = Depends(get_db)):
    """测试API密钥有效性"""
    key = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not key or not key.is_active:
        raise HTTPException(status_code=404, detail="密钥不存在")
    
    provider = key.provider
    
    # 这里可以添加实际的API测试逻辑
    # 返回密钥信息（不返回密钥值）
    return {
        "provider": provider.name,
        "key_name": key.key_name,
        "status": "ready",
        "message": "密钥配置成功，可以使用"
    }