"""Cleanup for tests that reset the legacy per-user model configuration."""
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.llm_config import LLMConfig
from app.models.model_center import ModelBinding


async def clear_user_model_configs(db: AsyncSession, *user_ids: str) -> None:
    await db.execute(delete(ModelBinding).where(
        ModelBinding.user_id.in_(user_ids), ModelBinding.scope_type == "user",
    ))
    await db.execute(delete(LLMConfig).where(LLMConfig.user_id.in_(user_ids)))
