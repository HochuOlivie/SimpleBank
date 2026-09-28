"""Service-level guarantees: all-or-nothing transfers and correctness under concurrency."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from typing import Any

import pytest
from django.db import connection
from django.db.models import Sum

from banking.exceptions import InsufficientFundsError
from banking.models import Account, Transaction, TransactionType, Transfer
from banking.services import transfer_money
from tests.helpers import PASSWORD
from users.services import register_user


def _account(email: str) -> Account:
    return Account.objects.get(owner__email=email)


def _ledger_balance(account: Account) -> Decimal:
    """The balance implied by the account's ledger entries."""

    def total(entry_type: TransactionType) -> Decimal:
        entries = account.transactions.filter(type=entry_type)
        return entries.aggregate(total=Sum("amount"))["total"] or Decimal(0)

    return total(TransactionType.CREDIT) - total(TransactionType.DEBIT)


@pytest.fixture
def accounts() -> tuple[Account, Account]:
    register_user("ada@example.com", PASSWORD)
    register_user("bob@example.com", PASSWORD)
    return _account("ada@example.com"), _account("bob@example.com")


@pytest.mark.django_db
def test_failure_midway_rolls_back_every_change(
    accounts: tuple[Account, Account], monkeypatch: pytest.MonkeyPatch
) -> None:
    ada, bob = accounts

    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("database went away")

    monkeypatch.setattr(Transaction.objects, "bulk_create", fail)

    with pytest.raises(RuntimeError):
        transfer_money(ada, bob, Decimal("100.00"))

    assert _account("ada@example.com").balance == Decimal("10000.00")
    assert _account("bob@example.com").balance == Decimal("10000.00")
    assert not Transfer.objects.exists()


def _run_concurrently(jobs: list[Callable[[], object]]) -> list[BaseException | None]:
    """Start all jobs at the same moment, each on its own thread and database connection."""
    barrier = Barrier(len(jobs))

    def run(job: Callable[[], object]) -> BaseException | None:
        try:
            barrier.wait()
            job()
            return None
        except Exception as exc:
            return exc
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        return list(pool.map(run, jobs))


@pytest.mark.django_db(transaction=True)
def test_concurrent_transfers_cannot_overdraw_an_account(
    accounts: tuple[Account, Account],
) -> None:
    ada, bob = accounts
    # Each transfer costs 2,000 + 50 fee; 10,000 covers exactly four of the ten.
    results = _run_concurrently(
        [lambda: transfer_money(ada, bob, Decimal("2000.00")) for _ in range(10)]
    )

    assert sum(result is None for result in results) == 4
    assert all(isinstance(r, InsufficientFundsError) for r in results if r is not None)
    ada, bob = _account("ada@example.com"), _account("bob@example.com")
    assert ada.balance == Decimal("1800.00")
    assert bob.balance == Decimal("18000.00")
    assert _ledger_balance(ada) == ada.balance
    assert _ledger_balance(bob) == bob.balance


@pytest.mark.django_db(transaction=True)
def test_opposite_concurrent_transfers_neither_deadlock_nor_lose_money(
    accounts: tuple[Account, Account],
) -> None:
    ada, bob = accounts
    jobs: list[Callable[[], object]] = []
    for _ in range(8):
        jobs.append(lambda: transfer_money(ada, bob, Decimal("100.00")))
        jobs.append(lambda: transfer_money(bob, ada, Decimal("100.00")))

    results = _run_concurrently(jobs)

    assert results == [None] * len(jobs)
    ada, bob = _account("ada@example.com"), _account("bob@example.com")
    # Each side sent 8 x 100 and received 8 x 100, paying 8 x 5 in fees.
    assert ada.balance == bob.balance == Decimal("9960.00")
    assert _ledger_balance(ada) == ada.balance
    assert _ledger_balance(bob) == bob.balance


@pytest.mark.django_db(transaction=True)
def test_simultaneous_retries_with_one_idempotency_key_transfer_once(
    accounts: tuple[Account, Account],
) -> None:
    ada, bob = accounts

    results = _run_concurrently(
        [
            lambda: transfer_money(ada, bob, Decimal("100.00"), idempotency_key="order-42")
            for _ in range(8)
        ]
    )

    assert results == [None] * 8
    assert Transfer.objects.count() == 1
    assert _account("ada@example.com").balance == Decimal("9895.00")
