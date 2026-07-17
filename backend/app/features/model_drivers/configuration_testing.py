"""Registry-backed compatibility routing for legacy configuration tests."""

from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy import desc, select

from app.features.model_config import ModelProfileContract
from app.features.model_drivers.domain import DriverContext, DriverTestResult
from app.features.model_drivers.executor import execute_connection_test
from app.features.model_drivers.registry import build_builtin_driver_registry
from app.models.model_center import ModelProfileVersion


_MODEL_TYPE_GROUPS = {
    "image": "image", "image-generation": "image", "image_generation": "image",
    "tts": "speech", "audio": "speech", "speech": "speech",
    "video": "video", "video-generation": "video", "video_generation": "video",
}
_BUILTIN_LLM_DRIVERS = {
    ("minimax", "text"): "minimax_text_v2",
    ("minimax", "image"): "minimax_image_v1",
    ("minimax", "speech"): "minimax_speech_v2",
    ("volcano", "image"): "volcano_ark_image_v3",
    ("volcano", "video"): "volcano_ark_video_v3",
    ("volcano", "speech"): "volcano_openspeech_v3",
    ("alibaba", "video"): "dashscope_video_v1",
    ("dashscope", "video"): "dashscope_video_v1",
    ("qwen", "video"): "dashscope_video_v1",
}


def select_llm_connection_driver_key(
    provider_id: str, model_type: str | None, *, persisted_driver_key: str | None = None,
) -> str:
    if persisted_driver_key and persisted_driver_key.strip():
        return persisted_driver_key.strip()
    group = _MODEL_TYPE_GROUPS.get(str(model_type or "").strip().lower(), "text")
    return _BUILTIN_LLM_DRIVERS.get((str(provider_id or "").strip().lower(), group), "legacy_text_v1")


def select_external_connection_driver_key(provider: Any, params: Mapping[str, Any]) -> str:
    persisted = str(params.get("driver_key") or "").strip()
    if persisted:
        return persisted
    provider_name = str(getattr(provider, "name", "") or "").strip().lower()
    storage_provider = str(params.get("storage_provider") or params.get("provider") or "").strip().lower()
    if provider_name == "local_ffmpeg":
        return "local_ffmpeg_v1"
    if provider_name == "object_storage" and storage_provider in {"qiniu", "kodo", "qiniu_kodo"}:
        return "qiniu_kodo_v1"
    return "external_adapter_v1"


async def resolve_published_driver_key(db: Any, legacy_model_id: str | None) -> str | None:
    if not legacy_model_id:
        return None
    result = await db.execute(
        select(ModelProfileVersion.driver_key).where(
            ModelProfileVersion.model_id == legacy_model_id,
            ModelProfileVersion.status == "published",
        ).order_by(desc(ModelProfileVersion.version), desc(ModelProfileVersion.id)).limit(1)
    )
    return result.scalar_one_or_none()


def build_connection_context(
    *, driver_key: str, provider_id: str, model_id: str, api_key: str,
    api_secret: str = "", base_url: str = "", connection_id: str | None = None,
    connection_params: Mapping[str, Any] | None = None,
) -> DriverContext:
    driver = build_builtin_driver_registry().require(driver_key)
    profile = ModelProfileContract(
        profile_version_id=f"config-test:{provider_id}:{model_id}", provider_id=provider_id,
        api_model_id=model_id, driver_key=driver_key, capabilities=driver.capabilities,
        input_contract={}, output_contract={}, parameter_schema={}, default_params={}, limits={}, pricing={},
        prompt_profile_key=None, contract_version="legacy-config-test-v1",
    )
    return DriverContext(
        profile, driver_key, connection_id, {"api_key": api_key, "api_secret": api_secret},
        base_url=base_url, connection_params=dict(connection_params or {}),
    )


def legacy_llm_test_response(result: DriverTestResult) -> dict[str, Any]:
    evidence = result.sanitized_evidence
    return {
        "success": result.status in {"connection_configured", "connection_verified"},
        "message": result.message,
        "response": evidence.get("response"),
        "response_time_ms": int(evidence.get("response_time_ms") or 0),
        "tokens_used": int(evidence.get("usage_count") or 0),
    }


async def execute_llm_connection_test(
    provider_id: str, api_key: str, model_id: str, message: str, *,
    model_type: str | None = None, driver_key: str | None = None, base_url: str = "",
    connection_params: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    selected_key = select_llm_connection_driver_key(
        provider_id, model_type, persisted_driver_key=driver_key,
    )
    params = {**dict(connection_params or {}), "test_message": message, "provider_name": provider_id}
    context = build_connection_context(
        driver_key=selected_key, provider_id=provider_id, model_id=model_id,
        api_key=api_key, base_url=base_url, connection_params=params,
    )
    result = await execute_connection_test(build_builtin_driver_registry(), selected_key, context)
    return legacy_llm_test_response(result)


__all__ = [
    "build_connection_context", "execute_llm_connection_test", "legacy_llm_test_response",
    "resolve_published_driver_key", "select_external_connection_driver_key",
    "select_llm_connection_driver_key",
]
