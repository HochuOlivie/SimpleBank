from functools import cached_property
from typing import TYPE_CHECKING, Any

from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.serializers import BaseSerializer

from banking.filters import TransactionFilter
from banking.models import Account, Transaction, Transfer
from banking.serializers import AccountSerializer, TransactionSerializer, TransferSerializer

if TYPE_CHECKING:
    _GenericView = generics.GenericAPIView[Any]
else:
    _GenericView = object


class OwnAccountMixin(_GenericView):
    """Gives a view the authenticated user's account, or a 404 for users without one
    (such as staff users created with ``createsuperuser``)."""

    @cached_property
    def account(self) -> Account:
        return get_object_or_404(Account, owner_id=self.request.user.pk)


class AccountView(OwnAccountMixin, generics.RetrieveAPIView[Account]):
    """The authenticated user's account, including its current balance."""

    serializer_class = AccountSerializer

    def get_object(self) -> Account:
        return self.account


class TransactionListView(OwnAccountMixin, generics.ListAPIView[Transaction]):
    """The authenticated user's transactions, newest first, optionally within a date range."""

    queryset = Transaction.objects.select_related(
        "transfer__sender_account", "transfer__recipient_account"
    )
    serializer_class = TransactionSerializer
    filterset_class = TransactionFilter

    def get_queryset(self) -> QuerySet[Transaction]:
        return super().get_queryset().filter(account=self.account)


@extend_schema_view(
    post=extend_schema(
        responses={
            201: TransferSerializer,
            400: OpenApiResponse(description="Invalid amount or recipient account."),
            409: OpenApiResponse(description="Balance does not cover amount plus fee."),
        }
    )
)
class TransferListCreateView(OwnAccountMixin, generics.ListCreateAPIView[Transfer]):
    """Send money to another account (POST), or list transfers you sent or received (GET).

    The sender is debited the amount plus a fee of 2.5% (minimum EUR 5.00); the
    recipient is credited the full amount.
    """

    queryset = Transfer.objects.select_related("sender_account", "recipient_account").order_by(
        "-created_at", "-id"
    )
    serializer_class = TransferSerializer

    def get_queryset(self) -> QuerySet[Transfer]:
        return (
            super()
            .get_queryset()
            .filter(Q(sender_account=self.account) | Q(recipient_account=self.account))
        )

    def perform_create(self, serializer: BaseSerializer[Transfer]) -> None:
        serializer.save(sender_account=self.account)
