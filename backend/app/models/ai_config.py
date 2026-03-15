"""
AI配置数据模型
支持API密钥、外部API、AI模型的统一管理
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, JSON
from sqlalchemy.sql import func

from app.core.database import Base


class APIKeyConfig(Base):
    """API密钥配置"""
    __tablename__ = "api_key_configs"
    
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    
    # 服务商信息
    provider = Column(String(50), nullable=False)  # volcano, openai, anthropic等
    provider_name = Column(String(100))  # 显示名称
    
    # 密钥信息（加密存储）
    api_key = Column(Text, nullable=False)  # 加密后的API Key
    api_secret = Column(Text)  # 可选的Secret
    
    # 状态
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # 是否为默认配置
    
    # 使用限制
    rate_limit = Column(Integer, default=60)  # 每分钟请求限制
    quota = Column(Integer)  # 配额限制
    used_quota = Column(Integer, default=0)  # 已使用配额
    
    # 元数据
    description = Column(Text)
    metadata = Column(JSON, default={})  # 额外配置
    
    # 时间戳
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_used_at = Column(DateTime)


class ExternalAPIConfig(Base):
    """外部API接入配置"""
    __tablename__ = "external_api_configs"
    
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    
    # API基本信息
    name = Column(String(100), nullable=False)  # 配置名称
    provider = Column(String(50), nullable=False)  # 服务商
    api_type = Column(String(50), nullable=False)  # image, video, text, audio
    
    # 端点配置
    base_url = Column(String(500), nullable=False)  # API基础URL
    endpoint = Column(String(200))  # 具体端点路径
    
    # 认证信息
    auth_type = Column(String(20), default="bearer")  # bearer, apikey, oauth2
    api_key_id = Column(String(36))  # 关联的APIKeyConfig ID
    
    # 请求配置
    headers = Column(JSON, default={})  # 自定义请求头
    timeout = Column(Integer, default=30)  # 超时时间(秒)
    retry_count = Column(Integer, default=3)  # 重试次数
    
    # 状态
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    
    # 元数据
    description = Column(Text)
    metadata = Column(JSON, default={})
    
    # 时间戳
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_tested_at = Column(DateTime)
    last_test_status = Column(String(20))  # success, failed


class AIModelConfig(Base):
    """AI模型配置"""
    __tablename__ = "ai_model_configs"
    
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    
    # 模型信息
    model_id = Column(String(100), nullable=False)  # 模型唯一标识
    model_name = Column(String(200), nullable=False)  # 显示名称
    provider = Column(String(50), nullable=False)  # 服务商
    
    # 模型类型
    model_type = Column(String(50), nullable=False)  # text-generation, image-generation, video-generation, embedding
    
    # 版本管理
    version = Column(String(50), default="latest")
    
    # 能力标签
    capabilities = Column(JSON, default=[])  # ["chat", "completion", "function-calling"]
    
    # 参数配置（默认参数）
    default_params = Column(JSON, default={})  # {"temperature": 0.7, "max_tokens": 2000}
    
    # 成本配置
    input_cost = Column(Integer)  # 每1000 tokens输入成本（分）
    output_cost = Column(Integer)  # 每1000 tokens输出成本（分）
    
    # 限制配置
    context_window = Column(Integer)  # 上下文窗口大小
    max_tokens = Column(Integer)  # 最大输出tokens
    
    # 关联配置
    external_api_id = Column(String(36))  # 关联的ExternalAPIConfig ID
    
    # 状态
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    is_favorite = Column(Boolean, default=False)
    
    # 元数据
    description = Column(Text)
    metadata = Column(JSON, default={})  # 模型元数据：参数范围、支持语言等
    
    # 时间戳
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ModelProviderPreset(Base):
    """模型提供商预设配置（系统预设）"""
    __tablename__ = "model_provider_presets"
    
    id = Column(String(36), primary_key=True)
    
    # 提供商信息
    provider = Column(String(50), nullable=False, unique=True)
    provider_name = Column(String(100), nullable=False)
    provider_name_cn = Column(String(100))
    
    # 支持的模型类型
    supported_types = Column(JSON, default=[])  # ["text", "image", "video", "audio"]
    
    # 预设配置
    base_url_template = Column(String(500))  # 基础URL模板
    auth_type = Column(String(20), default="bearer")
    default_headers = Column(JSON, default={})
    
    # 可用模型列表
    available_models = Column(JSON, default=[])  # [{"id": "...", "name": "...", "type": "..."}]
    
    # 是否启用
    is_active = Column(Boolean, default=True)
    is_builtin = Column(Boolean, default=True)  # 是否为内置预设
    
    # 元数据
    description = Column(Text)
    documentation_url = Column(String(500))
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
