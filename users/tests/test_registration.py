import re
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from banking.models import Transaction, TransactionKind, TransactionType
from config import settings as project_settings
from conftest import PASSWORD
from users.models import User

pytestmark = pytest.mark.django_db

URL = "/api/v1/auth/register/"
Register = Callable[[str], dict[str, Any]]


def test_registration_opens_an_account_with_the_welcome_bonus(api_client: APIClient) -> None:
    response = api_client.post(URL, {"email": "Ada@Example.com", "password": PASSWORD})

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ada@example.com"
    assert re.fullmatch(r"[1-9]\d{9}", body["account"]["number"])
    assert body["account"]["balance"] == "10000.00"
    assert body["account"]["currency"] == "EUR"
    assert "password" not in body

    bonus = Transaction.objects.get()
    assert bonus.account.number == body["account"]["number"]
    assert bonus.type == TransactionType.CREDIT
    assert bonus.kind == TransactionKind.WELCOME_BONUS
    assert bonus.amount == bonus.balance_after == Decimal("10000.00")


def test_password_is_stored_hashed_with_argon2(register: Register, settings: Settings) -> None:
    settings.PASSWORD_HASHERS = project_settings.PASSWORD_HASHERS
    register("ada@example.com")

    user = User.objects.get()
    assert user.password.startswith("argon2$")
    assert user.check_password(PASSWORD)


def test_each_user_gets_a_distinct_account_number(register: Register) -> None:
    numbers = {register(f"user{i}@example.com")["account"]["number"] for i in range(20)}

    assert len(numbers) == 20


def test_email_can_only_be_registered_once(api_client: APIClient, register: Register) -> None:
    register("ada@example.com")

    response = api_client.post(URL, {"email": "ADA@example.com", "password": PASSWORD})

    assert response.status_code == 400
    assert response.json() == {"email": ["A user with this email already exists."]}
    assert User.objects.count() == 1


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"email": "not-an-email", "password": PASSWORD}, "email"),
        ({"email": f"{'a' * 243}@example.com", "password": PASSWORD}, "email"),  # 255 chars
        ({"email": "ada@example.com", "password": "short"}, "password"),
        ({"email": "ada@example.com", "password": "password123"}, "password"),  # too common
        ({"email": "ada@example.com"}, "password"),
        ({"password": PASSWORD}, "email"),
    ],
)
def test_registration_validates_input(
    api_client: APIClient, payload: dict[str, str], field: str
) -> None:
    response = api_client.post(URL, payload)

    assert response.status_code == 400
    assert field in response.json()
    assert not User.objects.exists()


def test_failed_account_opening_rolls_back_the_user(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(owner: User) -> None:
        raise RuntimeError("account opening failed")

    monkeypatch.setattr("users.services.open_account", fail)
    api_client.raise_request_exception = False

    response = api_client.post(URL, {"email": "ada@example.com", "password": PASSWORD})

    assert response.status_code == 500
    assert not User.objects.exists()


def test_email_registered_concurrently_after_validation_is_a_400(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def lose_the_race(email: str, password: str) -> User:
        User.objects.create_user(email, password)  # the other request commits first
        raise IntegrityError("duplicate key value violates unique constraint")

    monkeypatch.setattr("users.serializers.register_user", lose_the_race)

    response = api_client.post(URL, {"email": "ada@example.com", "password": PASSWORD})

    assert response.status_code == 400
    assert response.json() == {"email": ["A user with this email already exists."]}


def test_other_integrity_errors_are_not_reported_as_a_taken_email(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def clash(email: str, password: str) -> User:
        raise IntegrityError("duplicate key value violates unique constraint on number")

    monkeypatch.setattr("users.serializers.register_user", clash)
    api_client.raise_request_exception = False

    response = api_client.post(URL, {"email": "ada@example.com", "password": PASSWORD})

    assert response.status_code == 500
