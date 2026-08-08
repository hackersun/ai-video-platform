from decimal import Decimal

import pytest

from app.features.billing.domain import (
    InvalidMoney,
    customer_charge_micros,
    micros_to_rmb_text,
    rmb_to_micros,
)


def test_money_contract_uses_integer_micros_and_fixed_chinese_display_precision() -> None:
    assert rmb_to_micros("1.234567") == 1_234_567
    assert rmb_to_micros(Decimal("0.0000005")) == 1
    assert micros_to_rmb_text(1_234_567) == "1.234567"


def test_customer_markup_snapshot_uses_basis_points_without_float_math() -> None:
    assert customer_charge_micros(1_000_000, 2500) == 1_250_000
    assert customer_charge_micros(1, 5000) == 2


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "1000000001"])
def test_money_contract_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(InvalidMoney):
        rmb_to_micros(value, positive=True)
