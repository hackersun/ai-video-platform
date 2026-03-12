"""
健康检查端点
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings

router = APIRouter()


@router.get("/")
async def health_check():
    """基础健康检查"""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }


@router.get("/db")
async def db_health_check(db: AsyncSession = Depends(get_db)):
    """数据库健康检查"""
    try:
        # 执行简单查询测试连接
        from sqlalchemy import text
        result = await db.execute(text("SELECT 1"))
        await result.scalar()
        
        return {
            "status": "healthy",
            "database": "connected",
            "service": settings.PROJECT_NAME
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }
