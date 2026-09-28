from django.db.models import QuerySet
from rest_framework import generics
from rest_framework.pagination import LimitOffsetPagination

from banking.filters import TransactionFilter
from banking.models import Account, Transaction
from banking.serializers import AccountSerializer, TransactionSerializer


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
