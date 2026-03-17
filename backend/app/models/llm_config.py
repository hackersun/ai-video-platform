"""
大模型配置数据模型
支持多模型接入配置
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, JSON, Float
from sqlalchemy.sql import func

from app.core.database import Base


class LLMProvider(Base):
    """大模型提供商"""
    __tablename__ = "llm_providers"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(50), nullable=False, unique=True)  # volcano, openai等
    name_cn = Column(String(100))  # 火山引擎
    name_en = Column(String(100))  # Volcano Engine
    
    # 提供商类型
    provider_type = Column(String(20), default="cloud")  # cloud, local
    
    # API配置
    base_url = Column(String(500))  # API基础URL
    auth_type = Column(String(20), default="bearer")  # bearer, apikey
    
    # 状态
    is_active = Column(Boolean, default=True)
    is_builtin = Column(Boolean, default=True)
    
    # 元数据
    description = Column(Text)
    website_url = Column(String(500))
    doc_url = Column(String(500))
    icon_url = Column(String(500))
    
    # 扩展配置
    config_schema = Column(JSON, default={})  # 配置项JSON Schema
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class LLMModel(Base):
    """大模型定义"""
    __tablename__ = "llm_models"
    
    id = Column(String(36), primary_key=True)
    provider_id = Column(String(36), nullable=False, index=True)
    
    # 模型标识
    model_id = Column(String(100), nullable=False)  # doubao-seed-1-8-251228
    model_name = Column(String(200), nullable=False)  # Doubao-Seed-1.8
    model_name_cn = Column(String(200))  # 豆包Seed-1.8
    
    # 模型类型
    model_type = Column(String(50), default="chat")  # chat, completion, embedding
    
    # 能力标签
    capabilities = Column(JSON, default=[])  # ["chat", "function_calling", "vision"]
    
    # 上下文窗口
    context_window = Column(Integer, default=4096)
    max_tokens = Column(Integer, default=2048)
    
    # 成本配置（每1000 tokens）
    input_cost_per_1k = Column(Float, default=0.0)  # 输入成本
    output_cost_per_1k = Column(Float, default=0.0)  # 输出成本
    
    # 支持的功能
    supports_streaming = Column(Boolean, default=True)
    supports_function_calling = Column(Boolean, default=False)
    supports_vision = Column(Boolean, default=False)
    supports_json_mode = Column(Boolean, default=False)
    
    # 状态
    is_active = Column(Boolean, default=True)
    is_recommended = Column(Boolean, default=False)
    
    # 元数据
    description = Column(Text)
    version = Column(String(50))
    release_date = Column(DateTime)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class LLMConfig(Base):
    """用户的大模型配置"""
    __tablename__ = "llm_configs"
    
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    
    # 关联模型
    model_id = Column(String(36), nullable=False)
    
    # 配置名称
    name = Column(String(100), nullable=False)  # 我的火山配置
    
    # API密钥（加密存储）
    api_key = Column(Text)  # 加密后的密钥
    api_secret = Column(Text)  # 可选的Secret
    
    # 自定义参数
    temperature = Column(Float, default=0.7)
    top_p = Column(Float, default=0.9)
    max_tokens = Column(Integer)
    
    # 额外配置
    extra_params = Column(JSON, default={})
    
    # 状态
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # 是否为默认配置
    
    # 使用统计
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime)
    
    # 测试状态
    test_status = Column(String(20))  # success, failed, pending
    test_message = Column(Text)
    tested_at = Column(DateTime)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class LLMUsageLog(Base):
    """大模型使用日志"""
    __tablename__ = "llm_usage_logs"
    
    id = Column(String(36), primary_key=True)
    config_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    
    # 请求信息
    request_type = Column(String(50))  # chat, completion
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    # 成本
    cost = Column(Float, default=0.0)  # 实际成本
    
    # 响应时间
    response_time_ms = Column(Integer)
    
    # 状态
    status = Column(String(20))  # success, error
    error_message = Column(Text)
    
    # 请求内容摘要
    prompt_summary = Column(Text)
    
    created_at = Column(DateTime, default=func.now())
