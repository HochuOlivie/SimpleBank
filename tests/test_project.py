import os
import subprocess
import sys

import pytest
from django.core.management import call_command
from drf_spectacular.generators import SchemaGenerator


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


def test_openapi_schema_documents_login_and_error_bodies() -> None:
    schema = SchemaGenerator().get_schema(request=None, public=True)
    paths = schema["paths"]

    login = paths["/api/v1/auth/token/"]["post"]["responses"]["200"]
    transfer_errors = paths["/api/v1/transfers/"]["post"]["responses"]

    assert login["content"]["application/json"]["schema"]["$ref"].endswith("TokenObtainPair")
    for status in ("401", "404", "409", "422"):
        error_schema = transfer_errors[status]["content"]["application/json"]["schema"]
        assert error_schema["$ref"] == "#/components/schemas/Error"
