from decimal import Decimal
from typing import Any

from rest_framework import serializers

from banking.models import Account, Transaction, Transfer
from banking.services import transfer_money


class AccountSerializer(serializers.ModelSerializer[Account]):
    balance = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)

    class Meta:
        model = Account
        fields = ("number", "balance", "currency")
        read_only_fields = fields


class TransactionSerializer(serializers.ModelSerializer[Transaction]):
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    balance_after = serializers.DecimalField(max_digits=18, decimal_places=2)
    timestamp = serializers.DateTimeField(source="created_at")
    counterparty_account = serializers.SerializerMethodField(
        help_text="The other account of a transfer; null for other kinds of transaction."
    )

    class Meta:
        model = Transaction
        fields = (
            "id",
            "type",
            "kind",
            "amount",
            "balance_after",
            "timestamp",
            "transfer",
            "counterparty_account",
        )
        read_only_fields = fields

    def get_counterparty_account(self, entry: Transaction) -> str | None:
        transfer = entry.transfer
        if transfer is None:
            return None
        if transfer.sender_account_id == entry.account_id:
            return transfer.recipient_account.number
        return transfer.sender_account.number


class TransferSerializer(serializers.ModelSerializer[Transfer]):
    sender_account: serializers.SlugRelatedField[Account] = serializers.SlugRelatedField(
        slug_field="number", read_only=True
    )
    recipient_account = serializers.SlugRelatedField(
        slug_field="number",
        queryset=Account.objects.all(),
        help_text="10-digit number of the account to send money to.",
        error_messages={"does_not_exist": "No account with this number exists."},
    )
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"), help_text="In EUR."
    )
    fee = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True, help_text="Paid by the sender."
    )
    total = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True, help_text="Debited from the sender."
    )

    class Meta:
        model = Transfer
        fields = (
            "id",
            "sender_account",
            "recipient_account",
            "amount",
            "fee",
            "total",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def create(self, validated_data: dict[str, Any]) -> Transfer:
        sender = Account.objects.get(owner_id=self.context["request"].user.pk)
        return transfer_money(
            sender=sender,
            recipient=validated_data["recipient_account"],
            amount=validated_data["amount"],
        )
