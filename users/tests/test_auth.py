
import pytest
from rest_framework.test import APIClient

from tests.helpers import PASSWORD, Register

pytestmark = pytest.mark.django_db


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


def test_invalid_token_is_rejected_with_an_error_code(api_client: APIClient) -> None:
    api_client.credentials(HTTP_AUTHORIZATION="Bearer not-a-token")

    response = api_client.get("/api/v1/account/")

    assert response.status_code == 401
    assert response.json()["code"] == "token_not_valid"
