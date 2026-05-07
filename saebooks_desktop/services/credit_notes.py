"""Credit notes service — thin wrappers over APIClient.

Each function constructs the query params / payload and calls the
appropriate REST verb.  Callers should catch ``ServerOfflineError``
and ``APIError`` from ``api_client`` if they want custom error handling.
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def list_credit_notes(
    client: APIClient,
    page: int = 1,
    page_size: int = 50,
    status_filter: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """Return a page of credit notes from ``GET /api/v1/credit_notes``.

    Args:
        client: Caller-supplied APIClient instance.
        page: 1-based page number.
        page_size: Items per page.
        status_filter: One of ``"draft"``, ``"posted"``, ``"voided"`` or
            ``None`` / ``""`` to return all statuses.
        date_from: ISO-8601 date string (inclusive lower bound on date).
        date_to: ISO-8601 date string (inclusive upper bound on date).

    Returns:
        List of credit note dicts (may be empty).
    """
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if status_filter:
        params["status"] = status_filter.lower()
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to

    data = client.get("/api/v1/credit_notes", params=params)
    return data.get("items", [])


def get_credit_note(client: APIClient, credit_note_id: str) -> dict[str, Any]:
    """Fetch a single credit note by id.

    Args:
        client: Caller-supplied APIClient instance.
        credit_note_id: Credit note UUID string.

    Returns:
        Credit note dict including a ``lines`` list.

    Raises:
        ServerOfflineError: If the server cannot be reached.
        APIError: On non-2xx response.
    """
    return client.get(f"/api/v1/credit_notes/{credit_note_id}")


def create_credit_note(client: APIClient, data: dict[str, Any]) -> dict[str, Any]:
    """POST /api/v1/credit_notes — create a new credit note.

    Args:
        client: Caller-supplied APIClient.
        data: Credit note payload dict (contact_id, date, lines, …).

    Returns:
        Created credit note dict from API.

    Raises:
        ServerOfflineError: If the server is unreachable.
        APIError: On non-2xx response.
    """
    return client.post("/api/v1/credit_notes", json=data)


def update_credit_note(
    client: APIClient,
    credit_note_id: str,
    data: dict[str, Any],
    etag: int,
) -> tuple[int, dict[str, Any]]:
    """PATCH /api/v1/credit_notes/{credit_note_id} with optimistic locking.

    Args:
        client: Caller-supplied APIClient.
        credit_note_id: Credit note UUID string.
        data: Partial credit note payload.
        etag: Current version integer for If-Match header.

    Returns:
        (status_code, credit_note_dict) — 200 on success, 409 on conflict.

    Raises:
        ServerOfflineError: If the server is unreachable.
        APIError: On non-2xx/non-409 response.
    """
    headers = {"If-Match": str(etag)}
    return client.patch(
        f"/api/v1/credit_notes/{credit_note_id}", json=data, headers=headers
    )


def post_credit_note(
    client: APIClient, credit_note_id: str, etag: int
) -> dict[str, Any]:
    """POST /api/v1/credit_notes/{credit_note_id}/post — transition DRAFT → POSTED.

    Args:
        client: Caller-supplied APIClient.
        credit_note_id: Credit note UUID string.
        etag: Current version integer for If-Match header.

    Returns:
        Updated credit note dict.

    Raises:
        ServerOfflineError: If the server is unreachable.
        APIError: On non-2xx response.
    """
    headers = {"If-Match": str(etag)}
    return client.post(
        f"/api/v1/credit_notes/{credit_note_id}/post", headers=headers
    )


def void_credit_note(
    client: APIClient, credit_note_id: str
) -> dict[str, Any]:
    """POST /api/v1/credit_notes/{credit_note_id}/void — void a posted credit note.

    Args:
        client: Caller-supplied APIClient.
        credit_note_id: Credit note UUID string.

    Returns:
        Updated credit note dict.

    Raises:
        ServerOfflineError: If the server is unreachable.
        APIError: On non-2xx response.
    """
    return client.post(f"/api/v1/credit_notes/{credit_note_id}/void")


def list_contacts_for_credit_note(client: APIClient) -> list[dict[str, Any]]:
    """GET /api/v1/contacts?type=Customer&limit=200.

    Returns:
        List of contact dicts with at minimum ``id`` and ``name``.
    """
    data = client.get("/api/v1/contacts", params={"type": "Customer", "limit": 200})
    if isinstance(data, list):
        return data
    return data.get("items", [])


def list_income_accounts_for_credit_note(client: APIClient) -> list[dict[str, Any]]:
    """GET /api/v1/accounts?account_type=Income.

    Returns:
        List of account dicts with at minimum ``id`` and ``name``.
    """
    data = client.get("/api/v1/accounts", params={"account_type": "Income"})
    if isinstance(data, list):
        return data
    return data.get("items", [])


def list_tax_codes_for_credit_note(client: APIClient) -> list[dict[str, Any]]:
    """GET /api/v1/tax_codes.

    Returns:
        List of tax code dicts with at minimum ``id``, ``code``, and ``rate``.
    """
    data = client.get("/api/v1/tax_codes")
    if isinstance(data, list):
        return data
    return data.get("items", [])
