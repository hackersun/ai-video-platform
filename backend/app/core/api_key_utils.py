"""
API Key 查找工具

提供统一的函数用于从用户的 LLMConfig 中获取（解密后的）API 密钥和 base_url。
"""

from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from fastapi import HTTPException, status


async def get_user_api_key(
    db: AsyncSession,
    user_id: str,
    provider_id: str,
    raise_if_missing: bool = True
) -> Tuple[Optional[str], Optional[str]]:
    """
    获取用户配置的 API 密钥和 base_url（解密后）。

    查找逻辑：
    1. 优先查找用户的默认配置（is_default=True）
    2. 其次查找任意活跃的配置
    3. 找不到时根据 raise_if_missing 决定是否抛出错误

    Returns:
        Tuple[api_key, base_url]

    Raises:
        HTTPException: 用户未配置且 raise_if_missing=True。
    """
    from app.models.llm_config import LLMConfig, LLMModel

    result = await db.execute(
        select(LLMConfig, LLMModel)
        .join(LLMModel, LLMConfig.model_id == LLMModel.id)
        .where(
            and_(
                LLMConfig.user_id == user_id,
                LLMConfig.is_active == True,
                LLMConfig.is_default == True,
                LLMModel.provider_id == provider_id,
            )
        )
        .limit(1)
    )
    row = result.first()

    if not row:
        result = await db.execute(
            select(LLMConfig, LLMModel)
            .join(LLMModel, LLMConfig.model_id == LLMModel.id)
            .where(
                and_(
                    LLMConfig.user_id == user_id,
                    LLMConfig.is_active == True,
                    LLMModel.provider_id == provider_id,
                )
            )
            .order_by(LLMConfig.created_at.desc())
            .limit(1)
        )
        row = result.first()

    if not row:
        if raise_if_missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"未找到 {provider_id} API Key 配置。"
                    "请前往【LLM 配置】页面添加 API Key 后重试。"
                ),
            )
        return None, None

    config, model = row
    api_key = config.get_api_key_decrypted()
    # base_url: 优先用户配置的 extra_params 中的 base_url，其次用模型定义的 base_url
    extra = config.extra_params or {}
    base_url = extra.get("base_url") or getattr(model, "base_url", None)
    return api_key, base_url


# ========== 各 Provider 便捷函数 ==========

async def get_user_volcano_api_key(db: AsyncSession, user_id: str) -> str:
    """获取用户配置的火山引擎 API 密钥（解密后）"""
    api_key, _ = await get_user_api_key(db, user_id, "volcano")
    return api_key


async def get_user_minimax_api_key(db: AsyncSession, user_id: str) -> str:
    """获取用户配置的 MiniMax API 密钥（解密后）"""
    api_key, _ = await get_user_api_key(db, user_id, "minimax")
    return api_key


async def get_user_openai_api_key(db: AsyncSession, user_id: str) -> str:
    """获取用户配置的 OpenAI API 密钥（解密后）"""
    api_key, _ = await get_user_api_key(db, user_id, "openai")
    return api_key


async def get_user_qianlian_api_key(db: AsyncSession, user_id: str) -> str:
    """获取用户配置的阿里百炼 API 密钥（解密后）"""
    api_key, _ = await get_user_api_key(db, user_id, "qianlian")
    return api_key


async def get_user_dashscope_api_key(db: AsyncSession, user_id: str) -> str:
    """获取用户配置的千问 API 密钥（解密后）"""
    api_key, _ = await get_user_api_key(db, user_id, "dashscope")
    return api_key

