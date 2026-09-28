"""Banking operations. Every function that changes balances runs in one database transaction."""

import secrets
from decimal import Decimal

from django.db.transaction import atomic
from rest_framework.exceptions import ValidationError

from banking.exceptions import InsufficientFundsError
from banking.models import Account, Transaction, TransactionKind, TransactionType, Transfer
from banking.money import transfer_fee
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


@atomic
def transfer_money(sender: Account, recipient: Account, amount: Decimal) -> Transfer:
    """Move ``amount`` from sender to recipient; the sender also pays the transfer fee.

    Both account rows are locked (SELECT ... FOR UPDATE) until the transaction ends, so
    concurrent transfers touching either account queue up behind this one and always see
    the latest balance. Locking in primary-key order means two opposite transfers between
    the same accounts cannot deadlock. Either every change below is committed, or none is.
    """
    if sender.pk == recipient.pk:
        raise ValidationError({"recipient_account": ["You cannot transfer to your own account."]})

    locked = Account.objects.select_for_update().filter(pk__in=(sender.pk, recipient.pk))
    accounts = {account.pk: account for account in locked.order_by("pk")}
    sender, recipient = accounts[sender.pk], accounts[recipient.pk]

    fee = transfer_fee(amount)
    if sender.balance < amount + fee:
        raise InsufficientFundsError

    sender.balance -= amount + fee
    recipient.balance += amount
    Account.objects.bulk_update([sender, recipient], ["balance"])

    transfer = Transfer.objects.create(
        sender_account=sender, recipient_account=recipient, amount=amount, fee=fee
    )
    Transaction.objects.bulk_create(
        [
            Transaction(
                account=sender,
                transfer=transfer,
                type=TransactionType.DEBIT,
                kind=TransactionKind.TRANSFER,
                amount=amount,
                balance_after=sender.balance + fee,
            ),
            Transaction(
                account=sender,
                transfer=transfer,
                type=TransactionType.DEBIT,
                kind=TransactionKind.TRANSFER_FEE,
                amount=fee,
                balance_after=sender.balance,
            ),
            Transaction(
                account=recipient,
                transfer=transfer,
                type=TransactionType.CREDIT,
                kind=TransactionKind.TRANSFER,
                amount=amount,
                balance_after=recipient.balance,
            ),
        ]
    )
    return transfer
