"""Shared test values and the signatures of the ``register`` and ``login`` fixtures."""

from collections.abc import Callable
from typing import Any

PASSWORD = "correct horse battery staple"

Register = Callable[[str], dict[str, Any]]  # email -> registration response body
Login = Callable[[str], None]  # email -> the API client now authenticates as that user
