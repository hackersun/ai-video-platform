"""Compatibility facade routing external config tests through built-in drivers."""

from app.features.model_drivers.configuration_testing import (
    build_connection_context,
    select_external_connection_driver_key,
)
from app.features.model_drivers.executor import execute_connection_test
from app.features.model_drivers.registry import build_builtin_driver_registry


async def execute_external_connection_test(
    config, provider, *, http_client_factory, dev_mode, which, public_url_check,
) -> tuple[str, str]:
    params = dict(config.extra_config or {})
    driver_key = select_external_connection_driver_key(provider, params)
    if driver_key == "external_adapter_v1":
        params.update({
            "config": config, "provider": provider, "http_client_factory": http_client_factory,
            "dev_mode": dev_mode, "which": which, "public_url_check": public_url_check,
        })
    context = build_connection_context(
        driver_key=driver_key, provider_id=getattr(provider, "id", provider.name),
        model_id=provider.name, api_key=config.get_api_key_decrypted(),
        api_secret=config.get_api_secret_decrypted(), connection_id=getattr(config, "id", None),
        base_url=(config.custom_base_url or getattr(provider, "base_url", None) or "").rstrip("/"),
        connection_params=params,
    )
    result = await execute_connection_test(build_builtin_driver_registry(), driver_key, context)
    status = str(result.sanitized_evidence.get("legacy_status") or "")
    if not status:
        status = "success" if result.status == "connection_verified" else (
            "configured" if result.status == "connection_configured" else "failed"
        )
    return status, result.message
