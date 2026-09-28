from typing import Any

import pytest
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from tests.helpers import PASSWORD, Login, Register


@pytest.fixture(autouse=True)
def fast_password_hashing(settings: Settings) -> None:
    """Argon2 is slow by design; tests that do not check hashing use a fast hasher."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def register(api_client: APIClient) -> Register:
    """Register a user through the API and return the response body."""

    def _register(email: str, password: str = PASSWORD) -> dict[str, Any]:
        response = api_client.post("/api/v1/auth/register/", {"email": email, "password": password})
        assert response.status_code == 201, response.content
        body: dict[str, Any] = response.json()
        return body

    return _register


@pytest.fixture
def login(api_client: APIClient) -> Login:
    """Log a registered user in; the API client then sends their access token."""

    def _login(email: str, password: str = PASSWORD) -> None:
        response = api_client.post("/api/v1/auth/token/", {"email": email, "password": password})
        assert response.status_code == 200, response.content
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['access']}")

    return _login
