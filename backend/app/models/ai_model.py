"""
AI模型相关数据模型
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, JSON, Float
from sqlalchemy.sql import func

from app.core.database import Base


class ModelConfig(Base):
    """AI模型配置"""
    __tablename__ = "model_configs"
    
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    
    # 模型信息
    model_id = Column(String(100), nullable=False)
    model_name = Column(String(200), nullable=False)
    provider = Column(String(50), nullable=False)
    
    # 配置
    api_key = Column(Text)
    base_url = Column(String(500))
    
    # 参数
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer)
    
    # 状态
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    
    # 元数据
    extra_config = Column(JSON, default={})
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ModelUsageLog(Base):
    """模型使用日志"""
    __tablename__ = "model_usage_logs"
    
    id = Column(String(36), primary_key=True)
    config_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    
    # 请求信息
    model = Column(String(100))
    request_type = Column(String(50))
    
    # Token使用
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    # 成本
    cost = Column(Float, default=0.0)
    
    # 响应时间
    response_time_ms = Column(Integer)
    
    # 状态
    status = Column(String(20))
    
    created_at = Column(DateTime, default=func.now())


class CostSettings(Base):
    """成本设置"""
    __tablename__ = "cost_settings"
    
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    
    # 模型ID
    model_id = Column(String(100), nullable=False)
    
    # 成本配置
    input_cost_per_1k = Column(Float, default=0.0)
    output_cost_per_1k = Column(Float, default=0.0)
    
    # 预算限制
    monthly_budget = Column(Float)
    alert_threshold = Column(Float, default=80.0)  # 百分比
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
