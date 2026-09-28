import os

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_no_missing_migrations() -> None:
    """Models and migrations must never drift apart."""
    call_command("makemigrations", "--check", "--dry-run", verbosity=0)


def test_openapi_schema_is_valid_and_complete() -> None:
    call_command("spectacular", "--validate", "--fail-on-warn", "--file", os.devnull)
