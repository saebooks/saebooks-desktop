"""Account ranges service — thin wrappers over APIClient.

Functions:
    list_account_ranges(client)            → list[dict]  — GET /api/v1/account_ranges
    create_account_range(client, data)     → dict         — POST /api/v1/account_ranges
    patch_account_range(client, id, data)  → dict         — PATCH /api/v1/account_ranges/{id}
    delete_account_range(client, id)       → int          — DELETE /api/v1/account_ranges/{id}
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def list_account_ranges(client: APIClient) -> list[dict[str, Any]]:
    """Return all account ranges from ``GET /api/v1/account_ranges``.

    Args:
        client: Caller-supplied APIClient instance.

    Returns:
        List of account range dicts (may be empty).
    """
    data = client.get("/api/v1/account_ranges")
    if isinstance(data, list):
        return data
    return data.get("items", [])


def create_account_range(
    client: APIClient, data: dict[str, Any]
) -> dict[str, Any]:
    """Create an account range via ``POST /api/v1/account_ranges``.

    Args:
        client: Caller-supplied APIClient instance.
        data: Payload dict with keys: name, range_type, from_code, to_code.

    Returns:
        The created account range dict.
    """
    return client.post("/api/v1/account_ranges", json=data)


def patch_account_range(
    client: APIClient, range_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Patch an account range via ``PATCH /api/v1/account_ranges/{id}``.

    Args:
        client: Caller-supplied APIClient instance.
        range_id: The account range's id.
        data: Partial payload dict.

    Returns:
        The updated account range dict.
    """
    _status, result = client.patch(f"/api/v1/account_ranges/{range_id}", json=data)
    return result


def delete_account_range(client: APIClient, range_id: str) -> int:
    """Delete an account range via ``DELETE /api/v1/account_ranges/{id}``.

    Args:
        client: Caller-supplied APIClient instance.
        range_id: The account range's id.

    Returns:
        HTTP status code.
    """
    return client.delete(f"/api/v1/account_ranges/{range_id}")
