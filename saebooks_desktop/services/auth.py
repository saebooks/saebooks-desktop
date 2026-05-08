"""Authentication service — login and token management.

Two paths in:

- ``login(client, email, password)`` POSTs to ``/api/v1/auth/login`` and
  returns a bearer token string.
- ``validate_token(client, token)`` GETs ``/api/v1/me`` with the token in
  the Authorization header and returns the decoded user payload.  Used by
  the first-run wizard's "I have a bearer token" path so a freshly
  bootstrap-admin'd installation (no password yet) can sign the user in
  with the token printed by the CLI.

Expected ``/api/v1/auth/login`` request::

    {"email": "...", "password": "..."}

Expected ``/api/v1/auth/login`` response (200 OK)::

    {"access_token": "...", "token_type": "bearer"}

Expected ``/api/v1/me`` response (200 OK)::

    {"id": "...", "email": "...", "tenant_id": "...", "role": "..."}
"""
from __future__ import annotations

from typing import Any

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


def validate_token(client: APIClient, token: str) -> dict[str, Any]:
    """Verify a bearer token by calling ``GET /api/v1/me``.

    Args:
        client: ``APIClient`` pointed at the target server.  The client's
            own token is overridden by *token* for this single call.
        token: Bearer token to validate.

    Returns:
        The decoded user payload (dict).  At minimum contains ``email``.

    Raises:
        APIError: if the token is invalid (401) or the server rejects it.
        ServerOfflineError: if the server is unreachable.
    """
    if not token.strip():
        raise APIError("Token is empty.", status_code=None)

    # Attach the supplied token via the headers parameter so we don't
    # mutate the client's own token.  APIClient.get only takes (path,
    # params) so we go via the underlying httpx Client to inject the
    # Authorization header for this single call.
    import httpx

    from saebooks_desktop.services.api_client import ServerOfflineError

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token.strip()}",
    }
    try:
        with httpx.Client(
            base_url=client._base_url,  # type: ignore[attr-defined]
            headers=headers,
            timeout=client._timeout,  # type: ignore[attr-defined]
        ) as c:
            r = c.get("/api/v1/me")
    except httpx.TransportError as exc:
        raise ServerOfflineError(f"Server unreachable: {exc}") from exc

    if r.status_code == 401:
        raise APIError(
            "Token rejected by server (401). It may have expired or be invalid.",
            status_code=401,
        )
    if not r.is_success:
        raise APIError(
            f"GET /api/v1/me returned {r.status_code}: {r.text[:200]}",
            status_code=r.status_code,
        )
    data = r.json()
    if not isinstance(data, dict):
        raise APIError("Unexpected /api/v1/me response shape.", status_code=None)
    return data
