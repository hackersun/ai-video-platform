"""
外部API配置模型
支持Midjourney、Runway、Suno、阿里千问等
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, JSON, Float
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.llm_config import decrypt_key, encrypt_key


class ExternalAPIProvider(Base):
    """外部API提供商预设"""
    __tablename__ = "external_api_providers"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(50), nullable=False, unique=True)  # midjourney, runway, suno, qwen
    name_cn = Column(String(100))
    
    # API类型
    api_type = Column(String(50), nullable=False)  # image, video, audio, text
    
    # 端点配置
    base_url = Column(String(500), nullable=False)
    api_version = Column(String(20), default="v1")
    
    # 认证方式
    auth_type = Column(String(20), default="bearer")  # bearer, apikey
    auth_header = Column(String(50), default="Authorization")
    
    # 状态
    is_active = Column(Boolean, default=True)
    is_builtin = Column(Boolean, default=True)
    
    # 元数据
    description = Column(Text)
    doc_url = Column(String(500))
    icon_url = Column(String(500))
    
    # 支持的模型
    supported_models = Column(JSON, default=[])
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ExternalAPIConfig(Base):
    """用户的外部API配置"""
    __tablename__ = "external_api_configs"
    
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    
    # 关联提供商
    provider_id = Column(String(36), nullable=False)
    
    # 配置名称
    name = Column(String(100), nullable=False)
    
    # API密钥（加密存储）
    api_key = Column(Text, nullable=False)
    api_secret = Column(Text)  # 可选
    
    # 自定义端点（可选）
    custom_base_url = Column(String(500))
    
    # 请求配置
    timeout = Column(Integer, default=60)
    retry_count = Column(Integer, default=3)
    
    # 使用限制
    rate_limit_per_minute = Column(Integer, default=60)
    monthly_quota = Column(Integer)
    used_quota = Column(Integer, default=0)
    
    # 状态
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    
    # 测试状态
    test_status = Column(String(20))  # success, failed, pending
    test_message = Column(Text)
    tested_at = Column(DateTime)
    
    # 使用统计
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime)
    
    # 元数据
    description = Column(Text)
    extra_config = Column(JSON, default={})
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def get_api_key_decrypted(self) -> str:
        if not self.api_key:
            return ""
        return decrypt_key(self.api_key)

    def set_api_key_encrypted(self, plain_key: str) -> None:
        self.api_key = encrypt_key(plain_key) if plain_key else ""

    def get_api_secret_decrypted(self) -> str:
        if not self.api_secret:
            return ""
        return decrypt_key(self.api_secret)

    def set_api_secret_encrypted(self, plain_secret: Optional[str]) -> None:
        self.api_secret = encrypt_key(plain_secret) if plain_secret else None


class ExternalAPIUsageLog(Base):
    """外部API使用日志"""
    __tablename__ = "external_api_usage_logs"
    
    id = Column(String(36), primary_key=True)
    config_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    
    # 请求信息
    provider = Column(String(50))
    model = Column(String(100))
    request_type = Column(String(50))  # image, video, audio, text
    
    # 请求参数摘要
    prompt_summary = Column(Text)
    
    # 响应信息
    status = Column(String(20))  # success, error
    result_url = Column(String(500))  # 生成结果的URL
    
    # 成本
    cost = Column(Float, default=0.0)
    
    # 响应时间
    response_time_ms = Column(Integer)
    
    # 错误信息
    error_message = Column(Text)
    
    created_at = Column(DateTime, default=func.now())
