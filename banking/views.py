from django.db.models import Q, QuerySet
from rest_framework import generics
from rest_framework.pagination import LimitOffsetPagination

from banking.filters import TransactionFilter
from banking.models import Account, Transaction, Transfer
from banking.serializers import AccountSerializer, TransactionSerializer, TransferSerializer


class AccountView(generics.RetrieveAPIView[Account]):
    """The authenticated user's account, including its current balance."""

    serializer_class = AccountSerializer

    def get_object(self) -> Account:
        return Account.objects.get(owner_id=self.request.user.pk)


class TransactionPagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 500


class TransactionListView(generics.ListAPIView[Transaction]):
    """The authenticated user's transactions, newest first, optionally within a date range."""

    serializer_class = TransactionSerializer
    filterset_class = TransactionFilter
    pagination_class = TransactionPagination

    def get_queryset(self) -> QuerySet[Transaction]:
        return Transaction.objects.filter(account__owner_id=self.request.user.pk).select_related(
            "transfer__sender_account", "transfer__recipient_account"
        )


class TransferListCreateView(generics.ListCreateAPIView[Transfer]):
    """Send money to another account (POST), or list transfers you sent or received (GET).

    The sender is debited the amount plus a fee of 2.5% (minimum EUR 5.00); the
    recipient is credited the full amount.
    """

    serializer_class = TransferSerializer
    pagination_class = TransactionPagination

    def get_queryset(self) -> QuerySet[Transfer]:
        user_id = self.request.user.pk
        return (
            Transfer.objects.filter(
                Q(sender_account__owner_id=user_id) | Q(recipient_account__owner_id=user_id)
            )
            .select_related("sender_account", "recipient_account")
            .order_by("-created_at", "-id")
        )
