from rest_framework import serializers

from banking.models import Account, Transaction


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
