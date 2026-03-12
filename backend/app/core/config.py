"""
应用配置
"""

from typing import List
from pydantic_settings import BaseSettings
from pydantic import validator


class Settings(BaseSettings):
    """应用配置类"""
    
    # 项目信息
    PROJECT_NAME: str = "AI视频平台"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # 数据库配置
    DATABASE_URL: str = "postgresql://postgres:postgres@postgres:5432/aivideo"
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Milvus配置
    MILVUS_HOST: str = "milvus"
    MILVUS_PORT: int = 19530
    
    # Neo4j配置
    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    
    # MinIO配置
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_NAME: str = "aivideo"
    
    # JWT配置
    JWT_SECRET: str = "dev-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # CORS配置
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # Celery配置
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"
    
    # AI服务配置
    TTS_PROVIDER: str = "edge"  # edge, elevenlabs
    IMAGE_PROVIDER: str = "local"  # local, midjourney
    VIDEO_PROVIDER: str = "local"  # local, runway
    MUSIC_PROVIDER: str = "local"  # local, suno
    
    # Edge TTS配置
    EDGE_TTS_VOICE: str = "zh-CN-XiaoxiaoNeural"
    
    # OpenAI配置（可选）
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4"
    
    @validator("ALLOWED_HOSTS", pre=True)
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# 全局配置实例
settings = Settings()
