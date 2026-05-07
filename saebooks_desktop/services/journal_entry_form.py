"""Journal entry form service — create, update, post, and account listing.

Thin wrappers over APIClient for JournalEntryForm to call.  Each function
takes a caller-supplied client so tests can inject mocks.
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def create_journal_entry(client: APIClient, data: dict[str, Any]) -> dict[str, Any]:
    """POST /api/v1/journal_entries — create a new journal entry.

    Args:
        client: Caller-supplied APIClient.
        data: Journal entry payload dict (entry_date, narration, reference, lines).

    Returns:
        Created journal entry dict from API.

    Raises:
        ServerOfflineError: If the server is unreachable.
        APIError: On non-2xx response.
    """
    return client.post("/api/v1/journal_entries", json=data)


def update_journal_entry(
    client: APIClient, je_id: str, data: dict[str, Any], etag: int
) -> tuple[int, dict[str, Any]]:
    """PATCH /api/v1/journal_entries/{je_id} with optimistic locking.

    Args:
        client: Caller-supplied APIClient.
        je_id: Journal entry UUID string.
        data: Partial journal entry payload.
        etag: Current version integer for If-Match header.

    Returns:
        (status_code, je_dict) — 200 on success, 409 on conflict.

    Raises:
        ServerOfflineError: If the server is unreachable.
        APIError: On non-2xx/non-409 response.
    """
    headers = {"If-Match": str(etag)}
    return client.patch(f"/api/v1/journal_entries/{je_id}", json=data, headers=headers)


def post_journal_entry(client: APIClient, je_id: str, etag: int) -> dict[str, Any]:
    """POST /api/v1/journal_entries/{je_id}/post — transition DRAFT → POSTED.

    Args:
        client: Caller-supplied APIClient.
        je_id: Journal entry UUID string.
        etag: Current version integer for If-Match header.

    Returns:
        Updated journal entry dict.

    Raises:
        ServerOfflineError: If the server is unreachable.
        APIError: On non-2xx response.
    """
    headers = {"If-Match": str(etag)}
    return client.post(f"/api/v1/journal_entries/{je_id}/post", headers=headers)


def list_all_accounts(client: APIClient) -> list[dict[str, Any]]:
    """GET /api/v1/accounts — all account types (no filter).

    Returns:
        List of account dicts with at minimum ``id`` and ``name``.
    """
    data = client.get("/api/v1/accounts")
    if isinstance(data, list):
        return data
    return data.get("items", [])
