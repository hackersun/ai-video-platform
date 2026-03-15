"""
初始化数据库 - 创建所有表
"""
import asyncio
from app.core.database import engine, Base
from app.models import user, novel, team, ai_model, provider, api_key


async def init_db():
    """创建所有数据库表"""
    async with engine.begin() as conn:
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)
        print("✅ 数据库表创建成功")


if __name__ == "__main__":
    asyncio.run(init_db())