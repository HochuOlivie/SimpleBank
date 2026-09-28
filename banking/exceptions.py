from rest_framework import status
from rest_framework.exceptions import APIException


class InsufficientFundsError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "insufficient_funds"
    default_detail = "The balance does not cover the amount plus the transfer fee."


class IdempotencyKeyReusedError(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = "idempotency_key_reused"
    default_detail = "This Idempotency-Key was already used for a different transfer."
