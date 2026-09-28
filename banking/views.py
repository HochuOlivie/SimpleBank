import re
from functools import cached_property
from typing import TYPE_CHECKING, Any

from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404
from django.urls import reverse
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
from config.schema import NO_ACCOUNT, NOT_AUTHENTICATED, VALIDATION_ERROR, ErrorSerializer

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


ACCOUNT_ERRORS = {401: NOT_AUTHENTICATED, 404: NO_ACCOUNT}


@extend_schema(responses={200: AccountSerializer, **ACCOUNT_ERRORS})
class AccountView(OwnAccountMixin, generics.RetrieveAPIView[Account]):
    """The authenticated user's account, including its current balance."""

    serializer_class = AccountSerializer

    def get_object(self) -> Account:
        return self.account


@extend_schema(
    responses={200: TransactionSerializer(many=True), 400: VALIDATION_ERROR, **ACCOUNT_ERRORS}
)
class TransactionListView(OwnAccountMixin, generics.ListAPIView[Transaction]):
    """The authenticated user's transactions, newest first, optionally within a date range."""

    queryset = Transaction.objects.select_related(
        "transfer__sender_account", "transfer__recipient_account"
    )
    serializer_class = TransactionSerializer
    filterset_class = TransactionFilter

    def get_queryset(self) -> QuerySet[Transaction]:
        return super().get_queryset().filter(account=self.account)


def own_transfers(transfers: QuerySet[Transfer], account: Account) -> QuerySet[Transfer]:
    """Transfers the account sent or received."""
    return transfers.filter(Q(sender_account=account) | Q(recipient_account=account))


@extend_schema_view(
    get=extend_schema(responses={200: TransferSerializer(many=True), **ACCOUNT_ERRORS}),
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
            400: VALIDATION_ERROR,
            409: OpenApiResponse(
                ErrorSerializer, description="The balance does not cover amount plus fee."
            ),
            422: OpenApiResponse(
                ErrorSerializer, description="The Idempotency-Key was used for another transfer."
            ),
            **ACCOUNT_ERRORS,
        },
    ),
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
        return own_transfers(super().get_queryset(), self.account)

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
            headers={"Location": reverse("transfer-detail", args=[transfer.pk])},
        )

    def _idempotency_key(self) -> str | None:
        key = self.request.headers.get("Idempotency-Key")
        if key is not None and not IDEMPOTENCY_KEY_PATTERN.fullmatch(key):
            raise ValidationError(
                {"Idempotency-Key": ["Must be 1 to 64 visible ASCII characters."]}
            )
        return key


@extend_schema(responses={200: TransferSerializer, **ACCOUNT_ERRORS})
class TransferDetailView(OwnAccountMixin, generics.RetrieveAPIView[Transfer]):
    """One transfer you sent or received; other users' transfers are not found."""

    queryset = Transfer.objects.select_related("sender_account", "recipient_account")
    serializer_class = TransferSerializer

    def get_queryset(self) -> QuerySet[Transfer]:
        return own_transfers(super().get_queryset(), self.account)
