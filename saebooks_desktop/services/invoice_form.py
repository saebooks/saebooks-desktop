"""Invoice form service — create, update, and post invoices.

Thin wrappers over APIClient for InvoiceForm to call.  Each function takes a
caller-supplied client so tests can inject mocks.
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def create_invoice(client: APIClient, data: dict[str, Any]) -> dict[str, Any]:
    """POST /api/v1/invoices — create a new invoice.

    Args:
        client: Caller-supplied APIClient.
        data: Invoice payload dict (contact_id, issue_date, due_date, lines, …).

    Returns:
        Created invoice dict from API.

    Raises:
        ServerOfflineError: If the server is unreachable.
        APIError: On non-2xx response.
    """
    return client.post("/api/v1/invoices", json=data)


def update_invoice(
    client: APIClient, invoice_id: str, data: dict[str, Any], etag: int
) -> tuple[int, dict[str, Any]]:
    """PATCH /api/v1/invoices/{invoice_id} with optimistic locking.

    Args:
        client: Caller-supplied APIClient.
        invoice_id: Invoice UUID string.
        data: Partial invoice payload.
        etag: Current version integer for If-Match header.

    Returns:
        (status_code, invoice_dict) — 200 on success, 409 on conflict.

    Raises:
        ServerOfflineError: If the server is unreachable.
        APIError: On non-2xx/non-409 response.
    """
    headers = {"If-Match": str(etag)}
    return client.patch(f"/api/v1/invoices/{invoice_id}", json=data, headers=headers)


def post_invoice(client: APIClient, invoice_id: str, etag: int) -> dict[str, Any]:
    """POST /api/v1/invoices/{invoice_id}/post — transition DRAFT → POSTED.

    Args:
        client: Caller-supplied APIClient.
        invoice_id: Invoice UUID string.
        etag: Current version integer for If-Match header.

    Returns:
        Updated invoice dict.

    Raises:
        ServerOfflineError: If the server is unreachable.
        APIError: On non-2xx response.
    """
    headers = {"If-Match": str(etag)}
    return client.post(f"/api/v1/invoices/{invoice_id}/post", headers=headers)


def list_income_accounts(client: APIClient) -> list[dict[str, Any]]:
    """GET /api/v1/accounts?account_type=Income.

    Returns:
        List of account dicts with at minimum ``id`` and ``name``.
    """
    data = client.get("/api/v1/accounts", params={"account_type": "Income"})
    if isinstance(data, list):
        return data
    return data.get("items", [])


def list_contacts_for_invoice(client: APIClient) -> list[dict[str, Any]]:
    """GET /api/v1/contacts?type=Customer&limit=200.

    Returns:
        List of contact dicts with at minimum ``id`` and ``name``.
    """
    data = client.get("/api/v1/contacts", params={"type": "Customer", "limit": 200})
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
