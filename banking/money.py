"""Money arithmetic. Amounts are ``Decimal`` in euros, never floats."""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
TRANSFER_FEE_RATE = Decimal("0.025")
MINIMUM_TRANSFER_FEE = Decimal("5.00")


def round_to_cents(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def transfer_fee(amount: Decimal) -> Decimal:
    """Fee for sending ``amount``: 2.5% of it, rounded half-up to the cent, but at least €5."""
    return max(round_to_cents(amount * TRANSFER_FEE_RATE), MINIMUM_TRANSFER_FEE)


def to_cents(amount: Decimal) -> int:
    """Convert euros to integer cents, refusing amounts that would need rounding."""
    if amount != amount.quantize(CENT):
        raise ValueError(f"{amount} has more precision than one cent")
    return int(amount * 100)


def from_cents(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(CENT)
