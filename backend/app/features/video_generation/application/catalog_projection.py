"""Project canonical model-center video bindings into the workbench catalog."""

from typing import Any

from app.features.model_config.public import (
    load_binding_candidates,
    load_connection,
    list_product_catalog,
    select_binding_candidate,
)
from app.features.model_config.domain import VERIFIED_CONNECTION_STATUSES
from app.features.model_drivers.public import DriverUnavailableError, build_builtin_driver_registry


def _driver_available(driver_key: str | None) -> bool:
    if not driver_key:
        return False
    try:
        build_builtin_driver_registry().require(driver_key)
    except DriverUnavailableError:
        return False
    return True


async def list_canonical_video_models(db: Any, user_id: str) -> list[dict[str, Any]]:
    catalog = await list_product_catalog(db, user_id, capability="video_generation")
    candidates = await load_binding_candidates(
        db, user_id=user_id, task="shot_video", capability="video_generation",
    )
    selected = select_binding_candidate(
        candidates, user_id=user_id, project_id=None, series_id=None,
    )
    by_profile = {candidate.profile_version_id: candidate for candidate in candidates}
    models: list[dict[str, Any]] = []
    for item in catalog.models:
        binding = by_profile.get(item.profile_version_id or "")
        if binding is None:
            continue
        connection = await load_connection(db, binding.connection_id)
        configured = bool(connection and connection.status in VERIFIED_CONNECTION_STATUSES)
        available = _driver_available(item.driver_key)
        models.append({
            "id": item.profile_version_id,
            "name": item.model_name, "name_cn": item.model_name, "display_name": item.model_name,
            "provider_id": item.provider_code, "provider_name": item.provider_name,
            "api_model_id": item.api_model_id, "model_id": item.api_model_id,
            "profile_version_id": item.profile_version_id,
            "model_profile_version_id": item.profile_version_id,
            "config_id": None, "model_config_id": None,
            "model_type": "video-generation", "model_capabilities": list(item.capabilities),
            "capabilities": list(item.capabilities), "limits": item.limits,
            "protocol": item.input_contract, "lane": "configured",
            "adapter_status": "available" if available else "planned",
            "is_configured": configured, "is_default": bool(selected and selected.id == binding.id),
            "test_status": "success" if configured else "pending",
            "test_message": None if configured else "供应商账号尚未通过连接验证",
            "key_available": configured,
        })
    return models


def prefer_canonical_video_models(
    legacy: list[dict[str, Any]], canonical: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    canonical_ids = {item["api_model_id"] for item in canonical}
    return [item for item in legacy if item["api_model_id"] not in canonical_ids] + canonical


__all__ = ["list_canonical_video_models", "prefer_canonical_video_models"]
