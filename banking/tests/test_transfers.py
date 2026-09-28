from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from rest_framework.test import APIClient

from banking.models import Account, Transaction, Transfer

pytestmark = pytest.mark.django_db

Register = Callable[[str], dict[str, Any]]
Login = Callable[[str], None]
URL = "/api/v1/transfers/"


@pytest.fixture
def bob_number(register: Register, login: Login) -> str:
    """Ada and Bob are registered; the client is logged in as Ada. Returns Bob's number."""
    register("ada@example.com")
    bob = register("bob@example.com")
    login("ada@example.com")
    number: str = bob["account"]["number"]
    return number


def _balance(email: str) -> Decimal:
    return Account.objects.get(owner__email=email).balance


def _history(email: str) -> list[tuple[str, str, Decimal, Decimal]]:
    entries = Transaction.objects.filter(account__owner__email=email).order_by("id")
    return [(e.type, e.kind, e.amount, e.balance_after) for e in entries]


def test_transfer_moves_money_and_charges_the_fee_to_the_sender(
    api_client: APIClient, bob_number: str
) -> None:
    response = api_client.post(URL, {"recipient_account": bob_number, "amount": "1000.00"})

    assert response.status_code == 201
    body = response.json()
    ada_number = Account.objects.get(owner__email="ada@example.com").number
    assert body["sender_account"] == ada_number
    assert body["recipient_account"] == bob_number
    assert (body["amount"], body["fee"], body["total"]) == ("1000.00", "25.00", "1025.00")

    assert _balance("ada@example.com") == Decimal("8975.00")
    assert _balance("bob@example.com") == Decimal("11000.00")


def test_transfer_records_debits_for_sender_and_a_credit_for_recipient(
    api_client: APIClient, bob_number: str
) -> None:
    api_client.post(URL, {"recipient_account": bob_number, "amount": "100.00"})

    assert _history("ada@example.com")[1:] == [
        ("debit", "transfer", Decimal("100.00"), Decimal("9900.00")),
        ("debit", "transfer_fee", Decimal("5.00"), Decimal("9895.00")),  # minimum fee
    ]
    assert _history("bob@example.com")[1:] == [
        ("credit", "transfer", Decimal("100.00"), Decimal("10100.00")),
    ]
    transfer = Transfer.objects.get()
    assert transfer.transactions.count() == 3


def test_transfer_shows_up_in_both_histories_with_the_counterparty(
    api_client: APIClient, bob_number: str, login: Login
) -> None:
    transfer_id = api_client.post(
        URL, {"recipient_account": bob_number, "amount": "100.00"}
    ).json()["id"]
    ada_number = Account.objects.get(owner__email="ada@example.com").number

    ada_history = api_client.get("/api/v1/account/transactions/").json()["results"]
    login("bob@example.com")
    bob_history = api_client.get("/api/v1/account/transactions/").json()["results"]

    assert [(e["kind"], e["type"], e["amount"]) for e in ada_history[:2]] == [
        ("transfer_fee", "debit", "5.00"),
        ("transfer", "debit", "100.00"),
    ]
    assert {e["counterparty_account"] for e in ada_history[:2]} == {bob_number}
    assert ada_history[0]["transfer"] == transfer_id
    assert bob_history[0]["counterparty_account"] == ada_number
    assert (bob_history[0]["type"], bob_history[0]["amount"]) == ("credit", "100.00")


def test_whole_balance_can_be_sent_when_it_covers_the_fee(
    api_client: APIClient, bob_number: str
) -> None:
    response = api_client.post(URL, {"recipient_account": bob_number, "amount": "9756.09"})

    assert response.status_code == 201
    assert response.json()["fee"] == "243.90"
    assert _balance("ada@example.com") == Decimal("0.01")


def test_transfer_fails_without_side_effects_when_funds_do_not_cover_the_fee(
    api_client: APIClient, bob_number: str
) -> None:
    # 9,800 + 245 fee exceeds the 10,000 balance even though the amount alone does not.
    response = api_client.post(URL, {"recipient_account": bob_number, "amount": "9800.00"})

    assert response.status_code == 409
    assert response.json()["code"] == "insufficient_funds"
    assert _balance("ada@example.com") == _balance("bob@example.com") == Decimal("10000.00")
    assert not Transfer.objects.exists()
    assert Transaction.objects.count() == 2  # just the two welcome bonuses


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"recipient_account": "0000000000", "amount": "10.00"}, "recipient_account"),
        ({"recipient_account": "123", "amount": "10.00"}, "recipient_account"),
        ({"amount": "10.00"}, "recipient_account"),
        ({"recipient_account": "BOB", "amount": "0.00"}, "amount"),
        ({"recipient_account": "BOB", "amount": "-5.00"}, "amount"),
        ({"recipient_account": "BOB", "amount": "1.001"}, "amount"),
        ({"recipient_account": "BOB", "amount": "ten"}, "amount"),
        ({"recipient_account": "BOB", "amount": "10000000000.00"}, "amount"),
        ({"recipient_account": "BOB"}, "amount"),
    ],
)
def test_transfer_validates_input(
    api_client: APIClient, bob_number: str, payload: dict[str, str], field: str
) -> None:
    if payload.get("recipient_account") == "BOB":
        payload["recipient_account"] = bob_number

    response = api_client.post(URL, payload)

    assert response.status_code == 400
    assert field in response.json()
    assert not Transfer.objects.exists()


def test_cannot_transfer_to_own_account(api_client: APIClient, bob_number: str) -> None:
    own_number = Account.objects.get(owner__email="ada@example.com").number

    response = api_client.post(URL, {"recipient_account": own_number, "amount": "10.00"})

    assert response.status_code == 400
    assert response.json() == {"recipient_account": ["You cannot transfer to your own account."]}
    assert _balance("ada@example.com") == Decimal("10000.00")


def test_transfers_require_authentication(api_client: APIClient, bob_number: str) -> None:
    api_client.credentials()

    response = api_client.post(URL, {"recipient_account": bob_number, "amount": "10.00"})

    assert response.status_code == 401
    assert not Transfer.objects.exists()


def test_transfer_list_shows_sent_and_received_transfers_only(
    api_client: APIClient, bob_number: str, register: Register, login: Login
) -> None:
    carol_number = register("carol@example.com")["account"]["number"]
    api_client.post(URL, {"recipient_account": bob_number, "amount": "10.00"})
    login("bob@example.com")
    api_client.post(URL, {"recipient_account": carol_number, "amount": "20.00"})

    response = api_client.get(URL)

    assert response.status_code == 200
    assert [t["amount"] for t in response.json()["results"]] == ["20.00", "10.00"]
    login("ada@example.com")
    assert [t["amount"] for t in api_client.get(URL).json()["results"]] == ["10.00"]


def test_retry_with_the_same_idempotency_key_does_not_send_twice(
    api_client: APIClient, bob_number: str
) -> None:
    payload = {"recipient_account": bob_number, "amount": "100.00"}
    first = api_client.post(URL, payload, HTTP_IDEMPOTENCY_KEY="order-42")

    retry = api_client.post(URL, payload, HTTP_IDEMPOTENCY_KEY="order-42")

    assert (first.status_code, retry.status_code) == (201, 200)
    assert retry.json() == first.json()
    assert Transfer.objects.count() == 1
    assert _balance("ada@example.com") == Decimal("9895.00")


def test_different_idempotency_keys_are_different_transfers(
    api_client: APIClient, bob_number: str
) -> None:
    payload = {"recipient_account": bob_number, "amount": "100.00"}

    api_client.post(URL, payload, HTTP_IDEMPOTENCY_KEY="order-1")
    api_client.post(URL, payload, HTTP_IDEMPOTENCY_KEY="order-2")
    api_client.post(URL, payload)  # no key: always a new transfer
    api_client.post(URL, payload)

    assert Transfer.objects.count() == 4


def test_idempotency_keys_are_scoped_to_the_sender(
    api_client: APIClient, bob_number: str, register: Register, login: Login
) -> None:
    carol_number = register("carol@example.com")["account"]["number"]
    first = api_client.post(
        URL, {"recipient_account": bob_number, "amount": "10.00"}, HTTP_IDEMPOTENCY_KEY="k"
    )
    login("bob@example.com")

    second = api_client.post(
        URL, {"recipient_account": carol_number, "amount": "10.00"}, HTTP_IDEMPOTENCY_KEY="k"
    )

    assert (first.status_code, second.status_code) == (201, 201)


def test_reusing_an_idempotency_key_for_another_transfer_is_rejected(
    api_client: APIClient, bob_number: str
) -> None:
    api_client.post(
        URL, {"recipient_account": bob_number, "amount": "10.00"}, HTTP_IDEMPOTENCY_KEY="k"
    )

    response = api_client.post(
        URL, {"recipient_account": bob_number, "amount": "20.00"}, HTTP_IDEMPOTENCY_KEY="k"
    )

    assert response.status_code == 422
    assert response.json()["code"] == "idempotency_key_reused"
    assert Transfer.objects.count() == 1


@pytest.mark.parametrize("key", ["", "x" * 65, "has space", "ключ"])
def test_malformed_idempotency_keys_are_rejected(
    api_client: APIClient, bob_number: str, key: str
) -> None:
    response = api_client.post(
        URL, {"recipient_account": bob_number, "amount": "10.00"}, HTTP_IDEMPOTENCY_KEY=key
    )

    assert response.status_code == 400
    assert "Idempotency-Key" in response.json()
    assert not Transfer.objects.exists()


def test_largest_allowed_transfer_is_serialised_with_its_fee(
    api_client: APIClient, bob_number: str
) -> None:
    Account.objects.filter(owner__email="ada@example.com").update(balance=Decimal("2e10"))

    response = api_client.post(URL, {"recipient_account": bob_number, "amount": "9999999999.99"})

    assert response.status_code == 201
    assert response.json()["total"] == "10249999999.99"
