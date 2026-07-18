"""Explicit registry for installed provider capability drivers."""

from collections.abc import Iterable

from app.features.model_drivers.domain import (
    CapabilityDriver,
    DriverRegistrationError,
    DriverUnavailableError,
)


class DriverRegistry:
    def __init__(self, drivers: Iterable[CapabilityDriver]):
        registered: dict[str, CapabilityDriver] = {}
        for driver in drivers:
            key = getattr(driver, "key", None)
            capabilities = getattr(driver, "capabilities", None)
            if not isinstance(key, str) or not key or not isinstance(capabilities, frozenset):
                raise DriverRegistrationError("driver registration requires a key and frozen capabilities")
            if key in registered:
                raise DriverRegistrationError(f"driver '{key}' is registered more than once")
            registered[key] = driver
        self._drivers = registered

    def require(self, key: str) -> CapabilityDriver:
        driver = self._drivers.get(key)
        if driver is None:
            raise DriverUnavailableError(key)
        return driver

    def descriptions(self) -> tuple[dict[str, object], ...]:
        """Return only safe, provider-neutral management fields."""
        return tuple(
            {
                "key": key,
                "capabilities": sorted(driver.capabilities),
                "parameter_schema": {},
                "contract_version": "driver-v1",
            }
            for key, driver in sorted(self._drivers.items())
        )


def build_builtin_driver_registry(additional_drivers: Iterable[CapabilityDriver] = ()) -> DriverRegistry:
    from app.features.model_drivers.adapters.dashscope_video import DashScopeVideoDriver
    from app.features.model_drivers.adapters.external_adapter import ExternalAdapterDriver
    from app.features.model_drivers.adapters.legacy_text import LegacyTextDriver
    from app.features.model_drivers.adapters.local_ffmpeg import LocalFFmpegDriver
    from app.features.model_drivers.adapters.minimax_image import MiniMaxImageDriver
    from app.features.model_drivers.adapters.minimax_speech import MiniMaxSpeechDriver
    from app.features.model_drivers.adapters.minimax_text import MiniMaxTextDriver
    from app.features.model_drivers.adapters.qiniu_kodo import QiniuKodoDriver
    from app.features.model_drivers.adapters.volcano_ark_image import VolcanoArkImageDriver
    from app.features.model_drivers.adapters.volcano_ark_video import VolcanoArkVideoDriver
    from app.features.model_drivers.adapters.volcano_openspeech import VolcanoOpenSpeechDriver

    return DriverRegistry([
        MiniMaxTextDriver(), MiniMaxImageDriver(), MiniMaxSpeechDriver(),
        VolcanoArkImageDriver(), VolcanoArkVideoDriver(), VolcanoOpenSpeechDriver(),
        DashScopeVideoDriver(), LocalFFmpegDriver(), QiniuKodoDriver(),
        LegacyTextDriver(), ExternalAdapterDriver(),
        *additional_drivers,
    ])


def describe_installed_drivers() -> tuple[dict[str, object], ...]:
    return build_builtin_driver_registry().descriptions()


__all__ = ["DriverRegistry", "build_builtin_driver_registry", "describe_installed_drivers"]
