"""Stable compatibility driver for external adapters without capability-specific drivers."""

from app.features.model_drivers.adapters._shared import unsupported_poll, unsupported_submit
from app.features.model_drivers.domain import DriverTestResult


class ExternalAdapterDriver:
    key = "external_adapter_v1"
    capabilities = frozenset({"external_configuration"})

    async def test_connection(self, context):
        from app.features.model_drivers.adapters.external_connection import test_external_connection

        params = context.connection_params
        status, message = await test_external_connection(
            params["config"], params["provider"],
            http_client_factory=params["http_client_factory"], dev_mode=params["dev_mode"],
            which=params["which"], public_url_check=params["public_url_check"],
        )
        normalized = {
            "configured": "connection_configured", "success": "connection_verified",
        }.get(status, "failed")
        return DriverTestResult(normalized, message, {"legacy_status": status})

    async def submit(self, _command, _context):
        return unsupported_submit()

    poll = staticmethod(unsupported_poll)
