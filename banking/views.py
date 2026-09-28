import re
from functools import cached_property
from typing import TYPE_CHECKING, Any

from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from banking.filters import TransactionFilter
from banking.models import Account, Transaction, Transfer
from banking.serializers import AccountSerializer, TransactionSerializer, TransferSerializer
from banking.services import transfer_money

IDEMPOTENCY_KEY_PATTERN = re.compile(r"[\x21-\x7e]{1,64}")  # 1-64 visible ASCII characters

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
        parameters=[
            OpenApiParameter(
                "Idempotency-Key",
                location=OpenApiParameter.HEADER,
                description=(
                    "Optional unique key (up to 64 visible ASCII characters, e.g. a UUID). "
                    "Retrying a request with the same key returns the original transfer "
                    "with 200 instead of sending the money again."
                ),
            )
        ],
        responses={
            201: TransferSerializer,
            200: OpenApiResponse(TransferSerializer, description="Idempotent retry."),
            400: OpenApiResponse(description="Invalid amount, recipient or Idempotency-Key."),
            409: OpenApiResponse(description="Balance does not cover amount plus fee."),
            422: OpenApiResponse(description="Idempotency-Key reused for another transfer."),
        },
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

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transfer, created = transfer_money(
            sender=self.account,
            recipient=serializer.validated_data["recipient_account"],
            amount=serializer.validated_data["amount"],
            idempotency_key=self._idempotency_key(),
        )
        return Response(
            self.get_serializer(transfer).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def _idempotency_key(self) -> str | None:
        key = self.request.headers.get("Idempotency-Key")
        if key is not None and not IDEMPOTENCY_KEY_PATTERN.fullmatch(key):
            raise ValidationError(
                {"Idempotency-Key": ["Must be 1 to 64 visible ASCII characters."]}
            )
        return key
