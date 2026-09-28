from decimal import Decimal

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from banking.fields import MoneyField


class Account(models.Model):
    """A user's single EUR account. ``balance`` is never negative (enforced by the database)."""

    number = models.CharField(
        max_length=10,
        unique=True,
        editable=False,
        validators=[RegexValidator(r"^\d{10}$", "Account numbers have exactly 10 digits.")],
    )
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="account"
    )
    balance = MoneyField(default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="EUR", editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(balance__gte=0), name="account_balance_non_negative"
            ),
        ]

    def __str__(self) -> str:
        return self.number


class Transfer(models.Model):
    """Money moved between two accounts. Its ledger entries point back to it."""

    sender_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="outgoing_transfers"
    )
    recipient_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="incoming_transfers"
    )
    amount = MoneyField()
    fee = MoneyField()
    idempotency_key = models.CharField(
        max_length=64,
        blank=True,
        default="",
        editable=False,
        help_text="Client-chosen key that makes retrying this transfer safe; empty if none.",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("sender_account", "idempotency_key"),
                condition=~Q(idempotency_key=""),
                name="transfer_idempotency_key_unique_per_sender",
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="transfer_amount_positive"),
            models.CheckConstraint(condition=Q(fee__gte=0), name="transfer_fee_non_negative"),
            models.CheckConstraint(
                condition=~Q(sender_account=F("recipient_account")),
                name="transfer_between_distinct_accounts",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.amount} {self.sender_account} -> {self.recipient_account}"

    @property
    def total(self) -> Decimal:
        """What the sender pays: the amount plus the fee."""
        return self.amount + self.fee


class TransactionType(models.TextChoices):
    CREDIT = "credit"
    DEBIT = "debit"


class TransactionKind(models.TextChoices):
    WELCOME_BONUS = "welcome_bonus"
    TRANSFER = "transfer"
    TRANSFER_FEE = "transfer_fee"


class Transaction(models.Model):
    """One immutable ledger entry on one account."""

    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="transactions")
    type = models.CharField(max_length=6, choices=TransactionType.choices)
    kind = models.CharField(max_length=13, choices=TransactionKind.choices)
    amount = MoneyField(help_text="Always positive; the type says which way it moved.")
    balance_after = MoneyField(help_text="Account balance right after this entry.")
    transfer = models.ForeignKey(
        Transfer,
        on_delete=models.PROTECT,
        related_name="transactions",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [models.Index(fields=("account", "-created_at"), name="transaction_history_idx")]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="transaction_amount_positive"),
            models.CheckConstraint(
                condition=Q(type__in=TransactionType.values), name="transaction_type_valid"
            ),
            models.CheckConstraint(
                condition=Q(kind__in=TransactionKind.values), name="transaction_kind_valid"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.type} {self.amount} on {self.account}"
