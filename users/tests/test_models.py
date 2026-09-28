import pytest

from users.models import User

pytestmark = pytest.mark.django_db


def test_create_user_normalises_email_and_hashes_password() -> None:
    user = User.objects.create_user("Ada@Example.COM", "correct horse battery staple")

    assert user.email == "ada@example.com"
    assert user.check_password("correct horse battery staple")
    assert not user.is_staff


def test_create_superuser() -> None:
    user = User.objects.create_superuser("root@example.com", "correct horse battery staple")

    assert user.is_staff
    assert user.is_superuser
