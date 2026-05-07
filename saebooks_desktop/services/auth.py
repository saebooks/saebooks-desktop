"""Authentication service — login and token management.

``login`` POSTs credentials to ``POST /api/v1/auth/login`` and returns the
bearer token string.

API note: ``/api/v1/auth/login`` is not yet confirmed in the API repo as of
E/8.  The service is implemented against the expected contract; tests mock
the HTTP layer.  When the API implements the endpoint, no changes are needed
here.

Expected request body::

    {"email": "...", "password": "..."}

Expected response (200 OK)::

    {"access_token": "...", "token_type": "bearer"}
"""
from __future__ import annotations

from saebooks_desktop.services.api_client import APIClient, APIError


def login(client: APIClient, email: str, password: str) -> str:
    """Authenticate with the API and return the bearer token.

    Args:
        client: ``APIClient`` pointed at the target server.
        email: User's email address.
        password: User's password (plain text — transported over TLS).

    Returns:
        The access token string.

    Raises:
        APIError: if login fails (bad credentials, server error, etc.).
        ServerOfflineError: if the server is unreachable.
    """
    payload = {"email": email, "password": password}
    data = client.post("/api/v1/auth/login", json=payload)
    token: str | None = None
    if isinstance(data, dict):
        token = data.get("access_token") or data.get("token")
    if not token:
        raise APIError(
            "Login response did not include an access_token field.",
            status_code=None,
        )
    return token
