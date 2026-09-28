from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from banking.models import Account, Transaction, Transfer


class ReadOnlyAdmin(admin.ModelAdmin[Any]):
    """Balances and ledger entries only change through banking services, never by hand."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(Account)
class AccountAdmin(ReadOnlyAdmin):
    list_display = ("number", "owner", "balance", "currency", "created_at")
    search_fields = ("number", "owner__email")


@admin.register(Transfer)
class TransferAdmin(ReadOnlyAdmin):
    list_display = ("id", "sender_account", "recipient_account", "amount", "fee", "created_at")
    search_fields = ("sender_account__number", "recipient_account__number")


@admin.register(Transaction)
class TransactionAdmin(ReadOnlyAdmin):
    list_display = ("id", "account", "type", "kind", "amount", "balance_after", "created_at")
    list_filter = ("type", "kind")
    search_fields = ("account__number",)
