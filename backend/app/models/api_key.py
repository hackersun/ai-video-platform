# API密钥模型 - 加密存储
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class APIKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=False)
    key_name = Column(String(100), nullable=False)
    _key_value = Column("key_value", Text, nullable=False)  # 加密存储
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    provider = relationship("Provider", back_populates="api_keys")
    
    @property
    def key_value(self) -> str:
        """获取解密的密钥 - 仅内部使用"""
        from app.core.security import decrypt_api_key
        return decrypt_api_key(self._key_value)
    
    @key_value.setter
    def key_value(self, value: str):
        """设置加密密钥"""
        from app.core.security import encrypt_api_key
        self._key_value = encrypt_api_key(value)
    
    def get_decrypted_key(self) -> str:
        """获取解密后的密钥供外部调用"""
        return self.key_value