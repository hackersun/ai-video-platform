"""Shared server-side connection test for one saved legacy model config.

Used by the legacy ``/llm/configs/{id}/test`` endpoint, the simple-setup test
endpoint and the one-click pipeline's automatic re-test. Never returns or logs
secrets; only the provider's status message is persisted.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider

SPEECH_TYPES = ("tts", "audio", "speech")


async def run_saved_config_test(
    db: AsyncSession, config: LLMConfig, model: LLMModel,
    message: str = "你好，请回复'连接成功'", *, commit: bool = True,
) -> dict:
    from app.api.v1.endpoints import llm_config as endpoint  # late: keeps test patch points
    from app.features.model_drivers import resolve_published_driver_key
    from app.services.deterministic_provider_fake import (
        deterministic_config_test_result, deterministic_provider_fake_enabled,
    )
    from app.services.volcano_speech_tts import configure_volcano_speech_endpoint

    provider = (
        await db.execute(select(LLMProvider).where(LLMProvider.id == model.provider_id))
    ).scalar_one_or_none()
    provider_id = provider.id if provider else model.provider_id
    if deterministic_provider_fake_enabled():
        result = deterministic_config_test_result(model.model_id)
    else:
        api_key = config.get_api_key_decrypted()
        if not api_key:
            result = {
                "success": False,
                "message": "API Key 为空或无法解密，请重新保存并验证该配置",
                "response": None, "response_time_ms": 0, "tokens_used": 0,
            }
        else:
            category = "speech" if model.model_type in SPEECH_TYPES else "default"
            extra = config.extra_params if isinstance(config.extra_params, dict) else {}
            configured = configure_volcano_speech_endpoint(
                extra.get("base_url") or model.base_url or (provider.base_url if provider else None), extra,
            ) if category == "speech" else ""
            driver_key = str(extra.get("driver_key") or "").strip() or await resolve_published_driver_key(db, model.id)
            result = await endpoint._execute_config_test(
                provider_id, api_key, model.model_id, message,
                category=category, model_type=model.model_type, driver_key=driver_key,
                base_url=configured or model.base_url or (provider.base_url if provider else "") or "",
                connection_params=extra,
            )
    config.test_status = "success" if result.get("success") else "failed"
    config.test_message = result.get("message")
    config.tested_at = utc_now()
    if commit:
        await db.commit()
    return result


__all__ = ["run_saved_config_test"]
