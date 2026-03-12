"""
日志配置
"""

import sys
from loguru import logger

from app.core.config import settings


def setup_logging():
    """配置日志"""
    # 移除默认处理器
    logger.remove()
    
    # 添加控制台输出
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL if hasattr(settings, 'LOG_LEVEL') else "INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        colorize=True,
    )
    
    # 添加文件日志
    logger.add(
        "logs/app.log",
        rotation="500 MB",
        retention="10 days",
        level="INFO",
        encoding="utf-8",
    )
    
    # 添加错误日志
    logger.add(
        "logs/error.log",
        rotation="100 MB",
        retention="30 days",
        level="ERROR",
        encoding="utf-8",
    )
    
    logger.info("日志系统初始化完成")
