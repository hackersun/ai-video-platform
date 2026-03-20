"""
初始化数据库表
"""
import asyncio
from app.core.database import Base, engine, sync_engine

def init_db():
    """同步方式创建所有表"""
    # 导入所有模型以确保它们被注册
    from app.models.character import Character
    from app.models.llm_config import LLMProvider, LLMModel, LLMConfig, LLMUsageLog
    from app.models.external_api import ExternalAPIConfig
    from app.models.ai_model import ModelConfig
    from app.api.v1.endpoints.novels import Novel
    from app.api.v1.endpoints.scripts import Script
    from app.api.v1.endpoints.chapters import Chapter
    from app.api.v1.endpoints.storyboards import Storyboard
    from app.api.v1.endpoints.shots import Shot
    
    # 创建所有表
    Base.metadata.create_all(bind=sync_engine)
    print("✅ 数据库表创建成功！")


async def init_db_async():
    """异步方式创建所有表"""
    # 导入所有模型
    from app.models.character import Character
    from app.models.llm_config import LLMProvider, LLMModel, LLMConfig, LLMUsageLog
    from app.models.external_api import ExternalAPIConfig
    from app.models.ai_model import ModelConfig
    from app.api.v1.endpoints.novels import Novel
    from app.api.v1.endpoints.scripts import Script
    from app.api.v1.endpoints.chapters import Chapter
    from app.api.v1.endpoints.storyboards import Storyboard
    from app.api.v1.endpoints.shots import Shot
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ 数据库表创建成功（异步）！")


if __name__ == "__main__":
    init_db()
