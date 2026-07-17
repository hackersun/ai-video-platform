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


__all__ = ["DriverRegistry"]
