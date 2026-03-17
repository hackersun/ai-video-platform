"""
数据库配置
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

# 将sqlite:///转换为aiosqlite:///
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./ai_video.db"

# 异步引擎
engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL, 
    echo=False,
)

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autocommit=False, 
    autoflush=False
)

Base = declarative_base()


async def get_db():
    """获取异步数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# 同步会话（用于初始化数据库等操作）
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sync_database_url = "sqlite:///./ai_video.db"
sync_engine = create_engine(sync_database_url, connect_args={"check_same_thread": False})
SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)