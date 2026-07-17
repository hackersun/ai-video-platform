"""Compatibility driver for existing connection-test callables."""

from app.features.model_drivers.adapters._shared import unsupported_poll, unsupported_submit
from app.features.model_config import ModelProfileContract
from app.features.model_drivers.domain import DriverContext, DriverTestResult
from app.features.model_drivers.executor import execute_connection_test
from app.features.model_drivers.registry import build_builtin_driver_registry


class ConnectionCallableDriver:
    capabilities = frozenset({"text_generation"})

    def __init__(self, key, tester):
        self.key = key
        self._tester = tester

    async def test_connection(self, context):
        legacy = await self._tester(context)
        evidence_result = dict(legacy)
        if "tokens_used" in evidence_result:
            evidence_result["usage_count"] = evidence_result.pop("tokens_used")
        return DriverTestResult(
            "connection_verified" if legacy.get("success") else "failed",
            str(legacy.get("message") or ""),
            {"legacy_result": evidence_result},
        )

    async def submit(self, _command, _context):
        return unsupported_submit()

    poll = staticmethod(unsupported_poll)


async def execute_legacy_connection_test(
    provider_id, api_key, model_id, base_url, tester,
) -> dict:
    driver_key = "legacy_config_connection_v1"
    driver = ConnectionCallableDriver(driver_key, tester)
    profile = ModelProfileContract(
        profile_version_id=f"legacy:{provider_id}:{model_id}", provider_id=provider_id,
        api_model_id=model_id, driver_key=driver_key, capabilities=frozenset({"text_generation"}),
        input_contract={}, output_contract={}, parameter_schema={}, default_params={}, limits={}, pricing={},
        prompt_profile_key=None, contract_version="legacy-config-test-v1",
    )
    context = DriverContext(profile, driver_key, None, {"api_key": api_key}, base_url=base_url)
    result = await execute_connection_test(build_builtin_driver_registry([driver]), driver_key, context)
    legacy = dict(result.sanitized_evidence["legacy_result"])
    if "usage_count" in legacy:
        legacy["tokens_used"] = legacy.pop("usage_count")
    return legacy


async def execute_external_connection_test(
    config, provider, *, http_client_factory, dev_mode, which, public_url_check,
) -> tuple[str, str]:
    from app.features.model_drivers.adapters.external_connection import test_external_connection

    async def legacy_test(_context):
        status, message = await test_external_connection(
            config, provider, http_client_factory=http_client_factory, dev_mode=dev_mode,
            which=which, public_url_check=public_url_check,
        )
        return {"success": status != "failed", "status": status, "message": message}

    provider_id = getattr(provider, "id", provider.name)
    driver_key = f"external_config_{provider.name}_v1"
    driver = ConnectionCallableDriver(driver_key, legacy_test)
    profile = ModelProfileContract(
        profile_version_id=f"legacy:{provider_id}", provider_id=provider_id,
        api_model_id=provider.name, driver_key=driver_key, capabilities=frozenset({"text_generation"}),
        input_contract={}, output_contract={}, parameter_schema={}, default_params={}, limits={}, pricing={},
        prompt_profile_key=None, contract_version="legacy-external-config-test-v1",
    )
    secrets = {
        "api_key": config.get_api_key_decrypted(), "api_secret": config.get_api_secret_decrypted(),
    }
    context = DriverContext(
        profile, driver_key, getattr(config, "id", None), secrets,
        base_url=(config.custom_base_url or getattr(provider, "base_url", None) or "").rstrip("/"),
        connection_params=config.extra_config or {},
    )
    result = await execute_connection_test(build_builtin_driver_registry([driver]), driver_key, context)
    legacy = result.sanitized_evidence["legacy_result"]
    return str(legacy["status"]), str(legacy["message"])
