# AI视频平台配置系统设计方案

## 一、需求分析

### 核心目标
**配置即用** - 用户配置API Key后可直接调用模型，无需额外开发

### 功能需求
1. **API密钥配置管理** - 支持多服务商密钥管理
2. **外部API接入配置** - 灵活配置不同API服务商
3. **AI模型配置管理** - 模型参数、温度、最大token等
4. **服务商支持** - 火山引擎、Doubao等

---

## 二、技术架构

### 系统架构图
```
┌─────────────────────────────────────────────────────────────────┐
│                        配置管理层                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   服务商配置  │  │   密钥管理    │  │   模型配置    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      配置存储层 (SQLite)                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      模型调用层                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  火山引擎     │  │   Doubao     │  │   OpenAI     │          │
│  │  Ark SDK     │  │   Seed API   │  │   API        │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、数据库设计

### 3.1 服务商配置表 (providers)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| code | VARCHAR(50) | 服务商代码: volcengine, doubao, openai |
| name | VARCHAR(100) | 显示名称 |
| description | TEXT | 描述 |
| base_url | VARCHAR(500) | API基础URL |
| is_active | BOOLEAN | 是否启用 |

### 3.2 API密钥配置表 (api_keys)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| provider_id | INTEGER | 外键，关联服务商 |
| key_name | VARCHAR(100) | 密钥名称 |
| key_value | TEXT | 加密存储的密钥 |
| is_default | BOOLEAN | 是否默认密钥 |
| is_active | BOOLEAN | 是否启用 |
| usage_count | INTEGER | 使用次数 |

### 3.3 AI模型配置表 (ai_models)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| provider_id | INTEGER | 外键，关联服务商 |
| model_code | VARCHAR(100) | 模型代码 |
| model_name | VARCHAR(200) | 显示名称 |
| model_type | VARCHAR(50) | 类型: llm, image, video |
| max_tokens | INTEGER | 最大token数 |
| temperature | FLOAT | 默认温度 |
| top_p | FLOAT | Top-p采样 |
| context_window | INTEGER | 上下文窗口 |
| is_default | BOOLEAN | 是否默认模型 |

---

## 四、后端实现

### 4.1 数据模型

```python
# backend/app/models/provider.py
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base
from sqlalchemy.sql import func

class Provider(Base):
    __tablename__ = "providers"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    base_url = Column(String(500))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    api_keys = relationship("APIKey", back_populates="provider")
    models = relationship("AIModel", back_populates="provider")
```

### 4.2 加密存储

```python
# backend/app/core/security.py
from cryptography.fernet import Fernet
import base64
import os

# 生成或获取加密密钥
def get_encryption_key():
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        key = Fernet.generate_key()
        # 首次生成时需要保存到环境变量或配置
    return base64.urlsafe_b64decode(key)

cipher_suite = Fernet(get_encryption_key())

def encrypt_api_key(key: str) -> str:
    return cipher_suite.encrypt(key.encode()).decode()

def decrypt_api_key(encrypted_key: str) -> str:
    return cipher_suite.decrypt(encrypted_key.encode()).decode()
```

### 4.3 API接口

```python
# backend/app/api/v1/endpoints/config.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.models.provider import Provider
from app.models.api_key import APIKey
from app.models.ai_model import AIModel
from app.schemas.config import (
    ProviderResponse, ProviderCreate,
    APIKeyResponse, APIKeyCreate,
    AIModelResponse, AIModelCreate
)

router = APIRouter(prefix="/config", tags=["配置管理"])

# ============ 服务商管理 ============

@router.get("/providers", response_model=List[ProviderResponse])
def list_providers(db: Session = Depends(get_db)):
    return db.query(Provider).filter(Provider.is_active == True).all()

@router.post("/providers", response_model=ProviderResponse)
def create_provider(provider: ProviderCreate, db: Session = Depends(get_db)):
    db_provider = Provider(**provider.dict())
    db.add(db_provider)
    db.commit()
    db.refresh(db_provider)
    return db_provider

# ============ API密钥管理 ============

@router.get("/keys", response_model=List[APIKeyResponse])
def list_api_keys(provider_id: int = None, db: Session = Depends(get_db)):
    query = db.query(APIKey).filter(APIKey.is_active == True)
    if provider_id:
        query = query.filter(APIKey.provider_id == provider_id)
    return query.all()

@router.post("/keys", response_model=APIKeyResponse)
def create_api_key(key: APIKeyCreate, db: Session = Depends(get_db)):
    from app.core.security import encrypt_api_key
    db_key = APIKey(
        provider_id=key.provider_id,
        key_name=key.key_name,
        key_value=encrypt_api_key(key.key_value),  # 加密存储
        is_default=key.is_default
    )
    db.add(db_key)
    db.commit()
    db.refresh(db_key)
    return db_key

@router.delete("/keys/{key_id}")
def delete_api_key(key_id: int, db: Session = Depends(get_db)):
    key = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="密钥不存在")
    key.is_active = False
    db.commit()
    return {"message": "删除成功"}

# ============ 模型管理 ============

@router.get("/models", response_model=List[AIModelResponse])
def list_models(provider_id: int = None, model_type: str = None, db: Session = Depends(get_db)):
    query = db.query(AIModel).filter(AIModel.is_active == True)
    if provider_id:
        query = query.filter(AIModel.provider_id == provider_id)
    if model_type:
        query = query.filter(AIModel.model_type == model_type)
    return query.all()

@router.post("/models", response_model=AIModelResponse)
def create_model(model: AIModelCreate, db: Session = Depends(get_db)):
    db_model = AIModel(**model.dict())
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    return db_model
```

---

## 五、火山引擎/Doubao集成

### 5.1 服务类

```python
# backend/app/services/llm_provider.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import requests
import os

class LLMProvider(ABC):
    """LLM提供商抽象基类"""
    
    @abstractmethod
    def chat_completion(self, model: str, messages: List[Dict], **kwargs) -> Dict:
        pass

class VolcengineProvider(LLMProvider):
    """火山引擎提供商"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://ark.cn-beijing.volces.com/api/v3"
    
    def chat_completion(self, model: str, messages: List[Dict], **kwargs) -> Dict:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4096)
        }
        response = requests.post(url, headers=headers, json=payload)
        return response.json()

class OpenAIProvider(LLMProvider):
    """OpenAI提供商"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.openai.com/v1"
    
    def chat_completion(self, model: str, messages: List[Dict], **kwargs) -> Dict:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4096)
        }
        response = requests.post(url, headers=headers, json=payload)
        return response.json()

# 提供商工厂
class LLMProviderFactory:
    PROVIDERS = {
        "volcengine": VolcengineProvider,
        "doubao": VolcengineProvider,  # Doubao也是火山引擎
        "openai": OpenAIProvider,
    }
    
    @staticmethod
    def get_provider(provider_code: str, api_key: str) -> LLMProvider:
        provider_class = LLMProviderFactory.PROVIDERS.get(provider_code)
        if not provider_class:
            raise ValueError(f"不支持的提供商: {provider_code}")
        return provider_class(api_key)
```

### 5.2 统一调用接口

```python
# backend/app/services/ai_service.py
from typing import List, Dict, Any
from app.services.llm_provider import LLMProviderFactory
from app.models.provider import Provider
from app.models.api_key import APIKey
from app.models.ai_model import AIModel
from app.core.security import decrypt_api_key
from sqlalchemy.orm import Session

class AIService:
    """AI服务统一入口"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def chat(self, model_id: int, messages: List[Dict], **kwargs) -> Dict:
        # 获取模型配置
        model = self.db.query(AIModel).filter(AIModel.id == model_id).first()
        if not model or not model.is_active:
            raise ValueError("模型不存在或已停用")
        
        # 获取API密钥
        api_key_obj = self.db.query(APIKey).filter(
            APIKey.provider_id == model.provider_id,
            APIKey.is_active == True,
            APIKey.is_default == True
        ).first()
        
        if not api_key_obj:
            raise ValueError("未配置API密钥")
        
        # 获取服务商
        provider = self.db.query(Provider).filter(Provider.id == model.provider_id).first()
        
        # 创建提供商实例
        llm_provider = LLMProviderFactory.get_provider(
            provider.code,
            decrypt_api_key(api_key_obj.key_value)
        )
        
        # 调用模型
        return llm_provider.chat_completion(
            model=model.model_code,
            messages=messages,
            temperature=kwargs.get("temperature", model.temperature),
            max_tokens=kwargs.get("max_tokens", model.max_tokens)
        )
```

---

## 六、前端配置页面

### 6.1 配置页面组件

```tsx
// frontend/src/app/settings/page.tsx
"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toaster";
import { 
  Key, 
  Plus, 
  Trash2, 
  Edit, 
  Check, 
  X,
  Server,
  Brain
} from "lucide-react";
import { useEffect } from "react";

interface Provider {
  id: number;
  code: string;
  name: string;
  description: string;
}

interface APIKey {
  id: number;
  provider_id: number;
  key_name: string;
  is_default: boolean;
}

interface AIModel {
  id: number;
  provider_id: number;
  model_code: string;
  model_name: string;
  model_type: string;
  max_tokens: number;
  temperature: number;
}

export default function SettingsPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [models, setModels] = useState<AIModel[]>([]);
  const [activeTab, setActiveTab] = useState("providers");
  const [newKey, setNewKey] = useState({ provider_id: 0, key_name: "", key_value: "" });

  useEffect(() => {
    // 加载配置数据
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [providersRes, keysRes, modelsRes] = await Promise.all([
        fetch("/api/v1/config/providers").then(r => r.json()),
        fetch("/api/v1/config/keys").then(r => r.json()),
        fetch("/api/v1/config/models").then(r => r.json())
      ]);
      setProviders(providersRes);
      setApiKeys(keysRes);
      setModels(modelsRes);
    } catch (error) {
      console.error("加载配置失败", error);
    }
  };

  const handleAddKey = async () => {
    if (!newKey.key_name || !newKey.key_value) {
      toast({ title: "请填写完整信息", variant: "error" });
      return;
    }
    
    try {
      await fetch("/api/v1/config/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newKey)
      });
      toast({ title: "添加成功", variant: "success" });
      setNewKey({ provider_id: 0, key_name: "", key_value: "" });
      loadData();
    } catch (error) {
      toast({ title: "添加失败", variant: "error" });
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] p-8">
      <h1 className="text-2xl font-bold mb-6">系统配置</h1>
      
      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        <Button 
          variant={activeTab === "providers" ? "primary" : "outline"}
          onClick={() => setActiveTab("providers")}
        >
          <Server className="w-4 h-4 mr-2" />
          服务商
        </Button>
        <Button 
          variant={activeTab === "keys" ? "primary" : "outline"}
          onClick={() => setActiveTab("keys")}
        >
          <Key className="w-4 h-4 mr-2" />
          API密钥
        </Button>
        <Button 
          variant={activeTab === "models" ? "primary" : "outline"}
          onClick={() => setActiveTab("models")}
        >
          <Brain className="w-4 h-4 mr-2" />
          AI模型
        </Button>
      </div>

      {/* API密钥管理 */}
      {activeTab === "keys" && (
        <Card>
          <CardHeader>
            <CardTitle>API密钥管理</CardTitle>
          </CardHeader>
          <CardContent>
            {/* 添加密钥表单 */}
            <div className="flex gap-4 mb-6">
              <select 
                className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-white"
                value={newKey.provider_id}
                onChange={(e) => setNewKey({...newKey, provider_id: Number(e.target.value)})}
              >
                <option value={0}>选择服务商</option>
                {providers.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
              <Input 
                placeholder="密钥名称" 
                value={newKey.key_name}
                onChange={(e) => setNewKey({...newKey, key_name: e.target.value})}
                className="w-48"
              />
              <Input 
                placeholder="API Key"
                type="password"
                value={newKey.key_value}
                onChange={(e) => setNewKey({...newKey, key_value: e.target.value})}
                className="w-80"
              />
              <Button onClick={handleAddKey}>
                <Plus className="w-4 h-4 mr-2" />
                添加
              </Button>
            </div>

            {/* 密钥列表 */}
            <div className="space-y-3">
              {apiKeys.map(key => (
                <div 
                  key={key.id}
                  className="flex items-center justify-between p-4 rounded-lg bg-white/5"
                >
                  <div>
                    <p className="font-medium">{key.key_name}</p>
                    <p className="text-sm text-white/40">
                      {providers.find(p => p.id === key.provider_id)?.name}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    {key.is_default && (
                      <span className="px-2 py-1 text-xs bg-green-500/20 text-green-400 rounded">
                        默认
                      </span>
                    )}
                    <Button variant="ghost" size="sm">
                      <Edit className="w-4 h-4" />
                    </Button>
                    <Button variant="ghost" size="sm" className="text-red-400">
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 模型管理 */}
      {activeTab === "models" && (
        <Card>
          <CardHeader>
            <CardTitle>AI模型配置</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {models.map(model => (
                <div 
                  key={model.id}
                  className="p-4 rounded-lg bg-white/5 border border-white/10"
                >
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-medium">{model.model_name}</h3>
                    <span className="text-xs px-2 py-1 bg-violet-500/20 text-violet-400 rounded">
                      {model.model_type}
                    </span>
                  </div>
                  <p className="text-sm text-white/40 mb-2">{model.model_code}</p>
                  <div className="text-xs text-white/60">
                    <p>最大Token: {model.max_tokens}</p>
                    <p>默认温度: {model.temperature}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

---

## 七、交付计划

### Day 1: 完成初版
- [x] 数据库模型设计
- [x] 后端API开发
- [x] 前端配置页面
- [ ] 测试验证

### Day 2: 测试验证
- [ ] API密钥加密测试
- [ ] 模型调用测试
- [ ] 前端界面测试

---

## 八、已支持的模型

| 服务商 | 模型代码 | 类型 | 说明 |
|--------|----------|------|------|
| 火山引擎 | doubao-seed-2.0-pro | LLM |Doubao Pro版 |
| 火山引擎 | doubao-seed-2.0lite | LLM | Doubao Lite版 |
| 火山引擎 | cv-pixel | Image | 图像生成 |
| OpenAI | gpt-4o | LLM | GPT-4o |
| OpenAI | gpt-4o-mini | LLM | GPT-4o-mini |
| OpenAI | dall-e-3 | Image | DALL-E 3 |

---

*方案版本: v1.0*  
*最后更新: 2026-03-15*