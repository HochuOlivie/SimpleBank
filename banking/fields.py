from decimal import Decimal
from typing import Any

from django.db import models
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.models.expressions import Expression

from banking.money import from_cents, to_cents


class MoneyField(models.BigIntegerField[Decimal | int, Decimal]):
    """A ``Decimal`` euro amount stored as a whole number of cents in a BIGINT column.

    Code only ever sees exact Decimals such as ``Decimal("10000.00")``, while the database
    holds integers, so balances can be neither rounded nor summed imprecisely.
    """

    def from_db_value(
        self, value: int | None, expression: Expression, connection: BaseDatabaseWrapper
    ) -> Decimal | None:
        return None if value is None else from_cents(value)

    def to_python(self, value: Any) -> Decimal | None:
        return None if value is None else Decimal(value)

    def get_prep_value(self, value: Any) -> int | None:
        return None if value is None else to_cents(Decimal(value))
