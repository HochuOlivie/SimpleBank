from typing import Any

from rest_framework.exceptions import ErrorDetail
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """DRF's handler, plus a machine-readable ``code`` next to every top-level ``detail``.

    For example ``{"detail": "Insufficient funds...", "code": "insufficient_funds"}``, so
    clients can branch on the code instead of parsing the human-readable message.
    """
    response = drf_exception_handler(exc, context)
    if response is not None and isinstance(response.data, dict):
        detail = response.data.get("detail")
        if isinstance(detail, ErrorDetail):
            response.data["code"] = detail.code
    return response
