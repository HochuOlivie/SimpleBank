from decimal import Decimal

import pytest

from banking.money import from_cents, to_cents, transfer_fee


@pytest.mark.parametrize(
    ("amount", "fee"),
    [
        ("0.01", "5.00"),  # tiny transfers pay the minimum
        ("100.00", "5.00"),  # 2.5% = 2.50, below the minimum
        ("200.00", "5.00"),  # 2.5% = 5.00, exactly the minimum
        ("200.40", "5.01"),  # 2.5% = 5.01, just above it
        ("1000.00", "25.00"),
        ("333.32", "8.33"),  # 8.333 rounds down
        ("333.00", "8.33"),  # 8.325 rounds half-up (banker's rounding would give 8.32)
        ("333.10", "8.33"),  # 8.3275 rounds up
    ],
)
def test_transfer_fee(amount: str, fee: str) -> None:
    assert transfer_fee(Decimal(amount)) == Decimal(fee)


def test_cents_round_trip() -> None:
    assert to_cents(Decimal("10000.00")) == 1_000_000
    assert to_cents(Decimal("0.1")) == 10
    assert from_cents(1_000_000) == Decimal("10000.00")
    assert str(from_cents(5)) == "0.05"


def test_to_cents_rejects_sub_cent_amounts() -> None:
    with pytest.raises(ValueError, match="precision"):
        to_cents(Decimal("1.005"))
