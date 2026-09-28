"""Shared OpenAPI response descriptions, matching what ``config.exceptions`` returns."""

from typing import Any

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse
from rest_framework import serializers


class ErrorSerializer(serializers.Serializer[Any]):
    detail = serializers.CharField(help_text="Human-readable message.")
    code = serializers.CharField(help_text="Machine-readable error code.")


VALIDATION_ERROR = OpenApiResponse(
    OpenApiTypes.OBJECT, description='Invalid input, as {"field": ["message", ...]}.'
)
NOT_AUTHENTICATED = OpenApiResponse(
    ErrorSerializer, description="Missing, invalid or expired access token."
)
NO_ACCOUNT = OpenApiResponse(ErrorSerializer, description="The user has no bank account.")
