from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from rest_framework.test import APIClient

from banking.models import Account, Transaction, TransactionKind, TransactionType

pytestmark = pytest.mark.django_db

Register = Callable[[str], dict[str, Any]]
Login = Callable[[str], None]
HISTORY_URL = "/api/v1/account/transactions/"


def test_account_shows_number_and_balance(
    api_client: APIClient, register: Register, login: Login
) -> None:
    registered = register("ada@example.com")

    login("ada@example.com")

    response = api_client.get("/api/v1/account/")

    assert response.status_code == 200
    assert response.json() == {
        "number": registered["account"]["number"],
        "balance": "10000.00",
        "currency": "EUR",
    }


@pytest.mark.parametrize("url", ["/api/v1/account/", HISTORY_URL])
def test_account_endpoints_require_authentication(api_client: APIClient, url: str) -> None:
    response = api_client.get(url)

    assert response.status_code == 401
    assert response["WWW-Authenticate"].startswith("Bearer")


def test_new_account_history_holds_the_welcome_bonus(
    api_client: APIClient, register: Register, login: Login
) -> None:
    register("ada@example.com")

    login("ada@example.com")

    response = api_client.get(HISTORY_URL)

    assert response.status_code == 200
    page = response.json()
    assert page["count"] == 1
    [bonus] = page["results"]
    assert bonus["type"] == "credit"
    assert bonus["kind"] == "welcome_bonus"
    assert bonus["amount"] == bonus["balance_after"] == "10000.00"
    assert bonus["transfer"] is None
    assert bonus["counterparty_account"] is None
    assert datetime.fromisoformat(bonus["timestamp"]).tzinfo is not None


def _add_entries(email: str, *timestamps: datetime) -> None:
    account = Account.objects.get(owner__email=email)
    Transaction.objects.bulk_create(
        Transaction(
            account=account,
            type=TransactionType.CREDIT,
            kind=TransactionKind.TRANSFER,
            amount=Decimal("1.00"),
            balance_after=account.balance,
            created_at=at,
        )
        for at in timestamps
    )


@pytest.fixture
def history(register: Register, login: Login) -> None:
    """Ada's ledger: today's bonus plus entries at noon UTC on 1, 2 and 3 March 2026."""
    register("ada@example.com")
    register("bob@example.com")
    days = [datetime(2026, 3, day, 12, tzinfo=UTC) for day in (1, 2, 3)]
    _add_entries("ada@example.com", *days)
    _add_entries("bob@example.com", *days)  # must never show up for Ada
    login("ada@example.com")


def _dates(api_client: APIClient, **params: str) -> list[str]:
    response = api_client.get(HISTORY_URL, params)
    assert response.status_code == 200, response.content
    return [item["timestamp"][:10] for item in response.json()["results"]]


@pytest.mark.usefixtures("history")
def test_history_is_newest_first_and_only_the_users_own(api_client: APIClient) -> None:
    dates = _dates(api_client)

    assert len(dates) == 4  # includes today's welcome bonus
    assert dates[1:] == ["2026-03-03", "2026-03-02", "2026-03-01"]


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        pytest.param(
            {"from": "2026-03-02", "to": "2026-03-02"}, ["2026-03-02"], id="date-is-whole-day"
        ),
        pytest.param({"to": "2026-03-02"}, ["2026-03-02", "2026-03-01"], id="only-to"),
        pytest.param(
            {"from": "2026-03-01T12:00:01Z", "to": "2026-03-03T12:00:00Z"},
            ["2026-03-03", "2026-03-02"],
            id="datetimes-inclusive",
        ),
        pytest.param(
            {"from": "2026-03-02T13:00:00+01:00", "to": "2026-03-02T13:00:00+01:00"},
            ["2026-03-02"],
            id="offsets",
        ),
        pytest.param(
            {"from": "2026-03-02T12:00:00", "to": "2026-03-02T12:00:00"},
            ["2026-03-02"],
            id="naive-is-utc",
        ),
    ],
)
@pytest.mark.usefixtures("history")
def test_history_filters_by_date_range(
    api_client: APIClient,
    params: dict[str, str],
    expected: list[str],
) -> None:
    assert _dates(api_client, **params) == expected


@pytest.mark.usefixtures("history")
def test_history_filter_with_only_from_is_open_ended(api_client: APIClient) -> None:
    dates = _dates(api_client, **{"from": "2026-03-02"})

    assert len(dates) == 3
    assert dates[1:] == ["2026-03-03", "2026-03-02"]


@pytest.mark.usefixtures("history")
def test_history_is_paginated(api_client: APIClient) -> None:
    response = api_client.get(HISTORY_URL, {"to": "2026-03-31", "limit": "2", "offset": "1"})

    page = response.json()
    assert page["count"] == 3
    assert page["next"] is None
    assert page["previous"] is not None
    assert [item["timestamp"][:10] for item in page["results"]] == ["2026-03-02", "2026-03-01"]


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"from": "2026-03-03", "to": "2026-03-01"}, "to"),
        ({"from": "yesterday"}, "from"),
        ({"to": "2026-02-30"}, "to"),
    ],
)
@pytest.mark.usefixtures("history")
def test_history_rejects_invalid_filters(
    api_client: APIClient, params: dict[str, str], field: str
) -> None:
    response = api_client.get(HISTORY_URL, params)

    assert response.status_code == 400
    assert field in response.json()
