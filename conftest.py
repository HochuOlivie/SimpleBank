from typing import Any

import pytest
from rest_framework.test import APIClient

PASSWORD = "correct horse battery staple"


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def register(api_client: APIClient) -> Any:
    """Register a user through the API and return the response body."""

    def _register(email: str, password: str = PASSWORD) -> dict[str, Any]:
        response = api_client.post("/api/v1/auth/register/", {"email": email, "password": password})
        assert response.status_code == 201, response.content
        body: dict[str, Any] = response.json()
        return body

    return _register
