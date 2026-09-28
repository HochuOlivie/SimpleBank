from decimal import Decimal

import pytest
from django.db import IntegrityError

from banking.models import Account
from users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def account() -> Account:
    owner = User.objects.create_user("ada@example.com", "correct horse battery staple")
    return Account.objects.create(owner=owner, number="1234567890", balance=Decimal("12.34"))


def test_money_is_stored_as_cents_and_read_back_as_decimal(account: Account) -> None:
    account.refresh_from_db()

    assert account.balance == Decimal("12.34")
    assert Account.objects.values_list("balance", flat=True).get() == Decimal("12.34")
    assert Account.objects.filter(balance__gt=Decimal("12.33")).exists()


def test_sub_cent_amounts_are_rejected(account: Account) -> None:
    account.balance = Decimal("0.001")

    with pytest.raises(ValueError, match="precision"):
        account.save()


def test_database_refuses_a_negative_balance(account: Account) -> None:
    account.balance = Decimal("-0.01")

    with pytest.raises(IntegrityError, match="account_balance_non_negative"):
        account.save()
