"""Integer-micro RMB contracts and billing errors."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


MICROS_PER_RMB = Decimal("1000000")
MAX_RMB = Decimal("1000000000")


class BillingError(ValueError):
    """Base customer-safe billing error."""


class InvalidMoney(BillingError):
    pass


class InsufficientFunds(BillingError):
    pass


class BillingLimitExceeded(BillingError):
    pass


class BillingConflict(BillingError):
    pass


def rmb_to_micros(value: Any, *, positive: bool = False) -> int:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise InvalidMoney("人民币金额格式无效") from error
    if not amount.is_finite() or abs(amount) > MAX_RMB or (positive and amount <= 0):
        raise InvalidMoney("人民币金额超出安全范围")
    return int((amount * MICROS_PER_RMB).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def micros_to_rmb_text(value: int) -> str:
    amount = Decimal(int(value)) / MICROS_PER_RMB
    return format(amount.quantize(Decimal("0.000001")), "f")


def customer_charge_micros(supplier_micros: int, markup_bps: int) -> int:
    if supplier_micros < 0 or not 0 <= markup_bps <= 100_000:
        raise InvalidMoney("计费金额或加价比例无效")
    multiplier = Decimal(10_000 + markup_bps) / Decimal(10_000)
    return int((Decimal(supplier_micros) * multiplier).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
