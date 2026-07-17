"""Trusted live-canary policy parsing and RMB normalization."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import os
from typing import Any


CENT = Decimal("0.01")


class InvalidAccountingInput(ValueError):
    pass


def money(value: Any, *, positive: bool = False) -> Decimal:
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount > Decimal("1000000000"):
            raise InvalidAccountingInput("RMB amount must be finite and bounded")
        amount = amount.quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as error:
        raise InvalidAccountingInput("invalid RMB amount") from error
    if amount < 0 or (positive and amount <= 0):
        raise InvalidAccountingInput(
            "RMB amount must be positive" if positive else "RMB amount must be non-negative"
        )
    return amount


def money_text(value: Decimal) -> str:
    return format(value, ".2f")


def trusted_live_canary_policy(
    requested: dict[str, Any], *, environ: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """Build a live policy exclusively from server-owned environment values."""
    cleaned = {
        key: value
        for key, value in (requested or {}).items()
        if value not in (None, "", {}, [])
    }
    if not cleaned:
        return {}
    if cleaned != {"profile": "isolated_live_canary"}:
        raise InvalidAccountingInput(
            "live canary request may contain only the isolated profile"
        )
    source = os.environ if environ is None else environ
    try:
        maximum = money(source["LIVE_CANARY_MAX_RMB"], positive=True)
        estimates = {
            capability: money(
                source[f"LIVE_CANARY_{capability.upper()}_ESTIMATE_RMB"],
                positive=True,
            )
            for capability in ("image", "video", "tts")
        }
        if source.get("LIVE_CANARY_TEXT_ESTIMATE_RMB"):
            estimates["text"] = money(
                source["LIVE_CANARY_TEXT_ESTIMATE_RMB"], positive=True
            )
    except KeyError as error:
        raise InvalidAccountingInput(
            f"missing trusted live canary setting: {error.args[0]}"
        ) from error
    return {
        "profile": "isolated_live_canary",
        "live_canary": True,
        "max_rmb": money_text(maximum),
        "estimates_rmb": {
            key: money_text(value) for key, value in estimates.items()
        },
    }
