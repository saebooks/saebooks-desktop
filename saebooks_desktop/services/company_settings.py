"""Company settings service — thin wrappers over APIClient.

Functions:
    get_company(client, company_id)  → dict  — GET /api/v1/companies/{id}
    patch_company(client, company_id, data) → dict  — PATCH /api/v1/companies/{id}
    list_tax_codes(client)  → list[dict]  — GET /api/v1/tax_codes
    get_current_user(client) → dict  — GET /api/v1/auth/me
    get_version(client) → dict  — GET /api/v1/version
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def get_company(client: APIClient, company_id: str) -> dict[str, Any]:
    """Return the company record for *company_id*.

    Raises:
        ServerOfflineError: if the server is unreachable.
        APIError: for non-2xx HTTP responses.
    """
    return client.get(f"/api/v1/companies/{company_id}")


def patch_company(
    client: APIClient, company_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    """PATCH the company record and return the updated record.

    Raises:
        ServerOfflineError: if the server is unreachable.
        APIError: for non-2xx HTTP responses.
    """
    _status, result = client.patch(f"/api/v1/companies/{company_id}", json=data)
    return result


def list_tax_codes(client: APIClient) -> list[dict[str, Any]]:
    """Return all tax codes from ``GET /api/v1/tax_codes``.

    Raises:
        ServerOfflineError: if the server is unreachable.
        APIError: for non-2xx HTTP responses.
    """
    data = client.get("/api/v1/tax_codes")
    if isinstance(data, list):
        return data
    return data.get("items", [])


def get_current_user(client: APIClient) -> dict[str, Any]:
    """Return the current authenticated user from ``GET /api/v1/auth/me``.

    Raises:
        ServerOfflineError: if the server is unreachable.
        APIError: for non-2xx HTTP responses.
    """
    return client.get("/api/v1/auth/me")


def get_version(client: APIClient) -> dict[str, Any]:
    """Return the server version info from ``GET /api/v1/version``.

    Raises:
        ServerOfflineError: if the server is unreachable.
        APIError: for non-2xx HTTP responses.
    """
    return client.get("/api/v1/version")
