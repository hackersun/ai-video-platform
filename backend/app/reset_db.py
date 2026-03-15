"""
重置数据库 - 删除并重新创建所有表
"""
import asyncio
from sqlalchemy import text
from app.core.database import engine, Base


async def reset_database():
    """删除并重新创建所有表"""
    async with engine.begin() as conn:
        # 删除所有表（使用CASCADE）
        await conn.execute(text("DROP TABLE IF EXISTS model_configs CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS model_usage_logs CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS cost_settings CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS api_keys CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS providers CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS ai_models CASCADE"))
        print("✅ 旧表已清理")
        
        # 重新创建所有表
        await conn.run_sync(Base.metadata.create_all)
        print("✅ 数据库表创建成功")


if __name__ == "__main__":
    asyncio.run(reset_database())