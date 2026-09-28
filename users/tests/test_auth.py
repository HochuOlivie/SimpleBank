from collections.abc import Callable
from typing import Any

import pytest
from rest_framework.test import APIClient

from conftest import PASSWORD

pytestmark = pytest.mark.django_db

Register = Callable[[str], dict[str, Any]]


def test_login_returns_access_and_refresh_tokens(api_client: APIClient, register: Register) -> None:
    register("ada@example.com")

    response = api_client.post(
        "/api/v1/auth/token/", {"email": "ADA@example.com", "password": PASSWORD}
    )

    assert response.status_code == 200
    assert set(response.json()) == {"access", "refresh"}


@pytest.mark.parametrize(
    ("email", "password"),
    [("ada@example.com", "wrong password"), ("nobody@example.com", PASSWORD)],
)
def test_login_rejects_bad_credentials(
    api_client: APIClient, register: Register, email: str, password: str
) -> None:
    register("ada@example.com")

    response = api_client.post("/api/v1/auth/token/", {"email": email, "password": password})

    assert response.status_code == 401
    assert "access" not in response.json()


def test_refresh_token_yields_a_new_access_token(api_client: APIClient, register: Register) -> None:
    register("ada@example.com")
    tokens = api_client.post(
        "/api/v1/auth/token/", {"email": "ada@example.com", "password": PASSWORD}
    ).json()

    response = api_client.post("/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]})

    assert response.status_code == 200
    assert "access" in response.json()
