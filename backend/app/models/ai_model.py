"""
AI模型配置
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, ForeignKey, DateTime, 
    Boolean, JSON, Float, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum

from app.core.database import Base


class ModelProvider(str, enum.Enum):
    """AI模型提供商"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AMAZON = "amazon"
    AZURE = "azure"
    VOLCENGINE = "volcengine"
    STABILITY = "stability"
    RUNWAY = "runway"
    PIKA = "pika"
    MIDJOURNEY = "midjourney"
    SUNO = "suno"
    ELEVENLABS = "elevenlabs"
    LOCAL = "local"  # 本地部署


class ModelCategory(str, enum.Enum):
    """模型类别"""
    TEXT_GENERATION = "text_generation"     # 文本生成
    IMAGE_GENERATION = "image_generation"   # 图像生成
    VIDEO_GENERATION = "video_generation"   # 视频生成
    VOICE_SYNTHESIS = "voice_synthesis"     # 语音合成
    MUSIC_GENERATION = "music_generation"   # 音乐生成
    IMAGE_UNDERSTANDING = "image_understanding"  # 图像理解


class ModelStatus(str, enum.Enum):
    """模型状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    BETA = "beta"


class AIModel(Base):
    """AI模型配置表"""

    __tablename__ = "ai_models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 基本信息
    name = Column(String(100), nullable=False)
    display_name = Column(String(100))  # 显示名称
    description = Column(Text)
    provider = Column(String(50), nullable=False)
    category = Column(String(50), nullable=False)
    
    # 模型标识
    model_id = Column(String(100))  # 供应商的模型ID
    version = Column(String(20))    # 模型版本
    
    # 能力
    capabilities = Column(JSON)  # ["text", "image", "video"]
    max_tokens = Column(Integer)
    input_price = Column(Float, default=0)   # 每1K tokens 价格
    output_price = Column(Float, default=0) # 每1K tokens 价格
    
    # 支持的参数
    supported_params = Column(JSON)  # 支持的参数列表
    default_params = Column(JSON)    # 默认参数
    
    # 状态
    status = Column(String(20), default=ModelStatus.ACTIVE)
    is_default = Column(Boolean, default=False)  # 是否为默认模型
    
    # 认证
    api_key_env = Column(String(100))  # API Key 环境变量名
    base_url = Column(String(500))    # API 基础URL
    
    # 限制
    rate_limit_rpm = Column(Integer, default=60)   # 每分钟请求限制
    rate_limit_tpm = Column(Integer, default=150000) # 每分钟tokens限制
    concurrent_limit = Column(Integer, default=10)  # 并发限制
    
    # 使用统计
    total_requests = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0)
    
    # 头像/图标
    icon_url = Column(String(500))
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<AIModel {self.provider}/{self.name}>"


class ModelConfig(Base):
    """用户/团队模型配置"""

    __tablename__ = "model_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 所属
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True)
    
    # 模型
    model_id = Column(UUID(as_uuid=True), ForeignKey("ai_models.id"), nullable=False)
    
    # 配置
    is_enabled = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # 优先级，数字越大越优先
    
    # 自定义参数
    custom_params = Column(JSON)  # 用户自定义参数
    custom_prompts = Column(JSON) # 自定义提示词
    
    # 使用限制
    daily_limit = Column(Integer, default=0)   # 每日限制，0表示无限
    monthly_limit = Column(Integer, default=0) # 每月限制
    
    # 统计
    today_usage = Column(Integer, default=0)
    month_usage = Column(Integer, default=0)
    last_used_at = Column(DateTime)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    model = relationship("AIModel")


class ModelUsageLog(Base):
    """模型使用日志"""

    __tablename__ = "model_usage_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 使用者
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True)
    
    # 模型
    model_id = Column(UUID(as_uuid=True), ForeignKey("ai_models.id"), nullable=False)
    config_id = Column(UUID(as_uuid=True), ForeignKey("model_configs.id"), nullable=True)
    
    # 请求信息
    request_type = Column(String(50))  # text_generation, image_generation 等
    prompt = Column(Text)
    response = Column(Text)
    
    # 消耗
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost = Column(Float, default=0)
    
    # 状态
    status = Column(String(20))  # success, failed, pending
    error_message = Column(Text)
    latency_ms = Column(Integer)  # 延迟(毫秒)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    user = relationship("User")
    model = relationship("AIModel")


class CostSettings(Base):
    """成本设置"""

    __tablename__ = "cost_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 所属
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True)
    
    # 路由策略
    routing_strategy = Column(String(50), default="balanced")  # balanced, quality_first, cost_first, speed_first
    
    # 预算设置
    daily_budget = Column(Float, default=0)     # 每日预算，0表示无限
    monthly_budget = Column(Float, default=0)   # 每月预算
    
    # 告警设置
    alert_threshold = Column(Float, default=0.8)  # 告警阈值(80%)
    
    # 自动切换
    auto_failover = Column(Boolean, default=True)  # 失败时自动切换
    fallback_to_free = Column(Boolean, default=True) # 失败时切换到免费模型
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)