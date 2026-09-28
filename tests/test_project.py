import os
import subprocess
import sys

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_no_missing_migrations() -> None:
    """Models and migrations must never drift apart."""
    call_command("makemigrations", "--check", "--dry-run", verbosity=0)


def test_openapi_schema_is_valid_and_complete() -> None:
    call_command("spectacular", "--validate", "--fail-on-warn", "--file", os.devnull)


def test_settings_refuse_to_start_without_a_secret_key_outside_debug() -> None:
    env = {k: v for k, v in os.environ.items() if k not in {"DJANGO_SECRET_KEY", "DJANGO_DEBUG"}}

    result = subprocess.run(
        [sys.executable, "-c", "import config.settings"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY must be set" in result.stderr
