# AI模型配置模型
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import json


class AIModel(Base):
    __tablename__ = "ai_models"
    
    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=False)
    model_code = Column(String(100), nullable=False, index=True)
    model_name = Column(String(200), nullable=False)
    model_type = Column(String(50))  # llm, image, video, audio
    description = Column(Text)
    max_tokens = Column(Integer, default=4096)
    temperature = Column(Float, default=0.7)
    top_p = Column(Float, default=0.9)
    context_window = Column(Integer, default=8192)
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    _config_json = Column("config_json", Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    provider = relationship("Provider", back_populates="models")
    
    @property
    def config(self) -> dict:
        """获取配置字典"""
        if self._config_json:
            return json.loads(self._config_json)
        return {}
    
    @config.setter
    def config(self, value: dict):
        """设置配置字典"""
        self._config_json = json.dumps(value) if value else None