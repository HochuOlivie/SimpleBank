"""Banking operations. Every function that changes balances runs in one database transaction."""

import secrets
from decimal import Decimal

from django.db.transaction import atomic

from banking.models import Account, Transaction, TransactionKind, TransactionType
from users.models import User

WELCOME_BONUS = Decimal("10000.00")


@atomic
def open_account(owner: User) -> Account:
    """Open the owner's account and credit it with the welcome bonus."""
    account = Account.objects.create(
        owner=owner, number=_unused_account_number(), balance=WELCOME_BONUS
    )
    Transaction.objects.create(
        account=account,
        type=TransactionType.CREDIT,
        kind=TransactionKind.WELCOME_BONUS,
        amount=WELCOME_BONUS,
        balance_after=account.balance,
    )
    return account


def _unused_account_number() -> str:
    # 9 billion possible numbers make a clash unlikely; the unique constraint backs this up.
    while True:
        number = str(secrets.randbelow(9 * 10**9) + 10**9)  # 10 digits, no leading zero
        if not Account.objects.filter(number=number).exists():
            return number
