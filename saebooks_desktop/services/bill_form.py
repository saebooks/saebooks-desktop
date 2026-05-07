"""Bill form service — create, update, and post bills.

Thin wrappers over APIClient for BillForm to call.  Each function takes a
caller-supplied client so tests can inject mocks.
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def create_bill(client: APIClient, data: dict[str, Any]) -> dict[str, Any]:
    """POST /api/v1/bills — create a new bill.

    Args:
        client: Caller-supplied APIClient.
        data: Bill payload dict (contact_id, issue_date, due_date, lines, …).

    Returns:
        Created bill dict from API.

    Raises:
        ServerOfflineError: If the server is unreachable.
        APIError: On non-2xx response.
    """
    return client.post("/api/v1/bills", json=data)


def update_bill(
    client: APIClient, bill_id: str, data: dict[str, Any], etag: int
) -> tuple[int, dict[str, Any]]:
    """PATCH /api/v1/bills/{bill_id} with optimistic locking.

    Args:
        client: Caller-supplied APIClient.
        bill_id: Bill UUID string.
        data: Partial bill payload.
        etag: Current version integer for If-Match header.

    Returns:
        (status_code, bill_dict) — 200 on success, 409 on conflict.

    Raises:
        ServerOfflineError: If the server is unreachable.
        APIError: On non-2xx/non-409 response.
    """
    headers = {"If-Match": str(etag)}
    return client.patch(f"/api/v1/bills/{bill_id}", json=data, headers=headers)


def post_bill(client: APIClient, bill_id: str, etag: int) -> dict[str, Any]:
    """POST /api/v1/bills/{bill_id}/post — transition DRAFT → POSTED.

    Args:
        client: Caller-supplied APIClient.
        bill_id: Bill UUID string.
        etag: Current version integer for If-Match header.

    Returns:
        Updated bill dict.

    Raises:
        ServerOfflineError: If the server is unreachable.
        APIError: On non-2xx response.
    """
    headers = {"If-Match": str(etag)}
    return client.post(f"/api/v1/bills/{bill_id}/post", headers=headers)


def list_expense_accounts(client: APIClient) -> list[dict[str, Any]]:
    """GET /api/v1/accounts?account_type=Expense.

    Returns:
        List of account dicts with at minimum ``id`` and ``name``.
    """
    data = client.get("/api/v1/accounts", params={"account_type": "Expense"})
    if isinstance(data, list):
        return data
    return data.get("items", [])


def list_suppliers(client: APIClient) -> list[dict[str, Any]]:
    """GET /api/v1/contacts?type=Supplier&limit=200.

    Returns:
        List of contact dicts with at minimum ``id`` and ``name``.
    """
    data = client.get("/api/v1/contacts", params={"type": "Supplier", "limit": 200})
    if isinstance(data, list):
        return data
    return data.get("items", [])


def list_tax_codes(client: APIClient) -> list[dict[str, Any]]:
    """GET /api/v1/tax_codes.

    Returns:
        List of tax code dicts with at minimum ``id``, ``code``, and ``rate``.
    """
    data = client.get("/api/v1/tax_codes")
    if isinstance(data, list):
        return data
    return data.get("items", [])
