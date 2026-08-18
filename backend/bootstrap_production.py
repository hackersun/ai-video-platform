"""Idempotently initialize shared production catalogs."""

import asyncio

from app.core.database import AsyncSessionLocal
from app.features.model_config.shared_catalog_projection import backfill_provider_catalog
from app.features.model_config.prompt_recovery import apply_prompt_recovery
from app.services.default_prompt_skills import (
    SYSTEM_PROMPT_SKILL_USER_ID,
    ensure_standard_prompt_skills,
)
from init_llm_config import init_llm_providers_and_models


async def bootstrap_shared_prompt_catalog() -> None:
    async with AsyncSessionLocal() as db:
        await backfill_provider_catalog(db, provider_ids={"deepseek", "minimax", "volcano"})
        await ensure_standard_prompt_skills(db, commit=False)
        await db.flush()
        await apply_prompt_recovery(db, user_id=SYSTEM_PROMPT_SKILL_USER_ID)
        await db.commit()


def main() -> None:
    init_llm_providers_and_models()
    asyncio.run(bootstrap_shared_prompt_catalog())
    print("✅ 生产公共模型与提示词目录初始化完成！")


if __name__ == "__main__":
    main()
