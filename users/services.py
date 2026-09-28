from django.db.transaction import atomic

from banking.services import open_account
from users.models import User


@atomic
def register_user(email: str, password: str) -> User:
    """Create the user together with their funded account: both exist, or neither does."""
    user = User.objects.create_user(email=email, password=password)
    open_account(user)
    return user
