from decimal import Decimal

import pytest

from banking.models import Account
from banking.services import open_account
from tests.helpers import PASSWORD
from users.models import User

pytestmark = pytest.mark.django_db


def test_open_account_draws_again_when_a_number_is_taken(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    taken = open_account(User.objects.create_user("ada@example.com", PASSWORD))
    draws = iter([int(taken.number) - 10**9, 123_456_789])  # a clash, then a free number
    monkeypatch.setattr("banking.services.secrets.randbelow", lambda _: next(draws))

    account = open_account(User.objects.create_user("bob@example.com", PASSWORD))

    assert account.number == "1123456789"
    assert account.balance == Decimal("10000.00")
    assert Account.objects.count() == 2
