"""Payment form service — create payment and fetch supporting reference data.

Thin wrappers over APIClient for PaymentForm to call.  Each function takes a
caller-supplied client so tests can inject mocks.

POST body shape (PaymentCreate):
    contact_id:       UUID (required)
    bank_account_id:  UUID (required)
    payment_date:     ISO date (required)
    amount:           Decimal (required)
    direction:        "INCOMING" | "OUTGOING"  (uppercased by API)
    method:           "cash" | "cheque" | "eft" | "credit_card" | "bpay" | "other"
    reference:        str | None
    notes:            str | None
    currency:         str (default "AUD")
    allocations:      list of {invoice_id?, bill_id?, credit_note_id?, amount}
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def create_payment(client: APIClient, data: dict[str, Any]) -> dict[str, Any]:
    """POST /api/v1/payments — record a new payment.

    Args:
        client: Caller-supplied APIClient.
        data: Payment payload dict.  Required keys: ``contact_id``,
            ``bank_account_id``, ``payment_date``, ``amount``, ``direction``,
            ``method``.

    Returns:
        Created payment dict from API.

    Raises:
        ServerOfflineError: If the server is unreachable.
        APIError: On non-2xx response.
    """
    return client.post("/api/v1/payments", json=data)


def list_bank_accounts(client: APIClient) -> list[dict[str, Any]]:
    """GET /api/v1/bank_accounts.

    Returns:
        List of bank account dicts with at minimum ``id`` and ``name``.
    """
    data = client.get("/api/v1/bank_accounts")
    if isinstance(data, list):
        return data
    return data.get("items", [])


def list_open_invoices(client: APIClient, contact_id: str) -> list[dict[str, Any]]:
    """GET /api/v1/invoices?contact_id=X&status=posted — open AR invoices.

    Args:
        client: Caller-supplied APIClient.
        contact_id: UUID string of the customer contact.

    Returns:
        List of posted (unpaid) invoice dicts.
    """
    data = client.get(
        "/api/v1/invoices",
        params={"contact_id": contact_id, "status": "posted", "limit": 200},
    )
    if isinstance(data, list):
        return data
    return data.get("items", [])


def list_open_bills(client: APIClient, contact_id: str) -> list[dict[str, Any]]:
    """GET /api/v1/bills?contact_id=X&status=posted — open AP bills.

    Args:
        client: Caller-supplied APIClient.
        contact_id: UUID string of the supplier contact.

    Returns:
        List of posted (unpaid) bill dicts.
    """
    data = client.get(
        "/api/v1/bills",
        params={"contact_id": contact_id, "status": "posted", "limit": 200},
    )
    if isinstance(data, list):
        return data
    return data.get("items", [])


def get_invoice_balance(client: APIClient, invoice_id: str) -> float:
    """GET /api/v1/invoices/{id} and return the outstanding balance.

    Falls back to ``total`` if ``outstanding`` / ``amount_due`` not present.

    Args:
        client: Caller-supplied APIClient.
        invoice_id: Invoice UUID string.

    Returns:
        Outstanding amount as a float (0.0 on error).
    """
    try:
        data = client.get(f"/api/v1/invoices/{invoice_id}")
    except Exception:  # noqa: BLE001
        return 0.0
    for key in ("outstanding", "amount_due", "amount_outstanding", "total"):
        val = data.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
    return 0.0


def get_bill_balance(client: APIClient, bill_id: str) -> float:
    """GET /api/v1/bills/{id} and return the outstanding balance.

    Args:
        client: Caller-supplied APIClient.
        bill_id: Bill UUID string.

    Returns:
        Outstanding amount as a float (0.0 on error).
    """
    try:
        data = client.get(f"/api/v1/bills/{bill_id}")
    except Exception:  # noqa: BLE001
        return 0.0
    for key in ("outstanding", "amount_due", "amount_outstanding", "total"):
        val = data.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
    return 0.0


def list_customers(client: APIClient) -> list[dict[str, Any]]:
    """GET /api/v1/contacts?type=Customer&limit=200.

    Returns:
        List of customer contact dicts.
    """
    data = client.get("/api/v1/contacts", params={"type": "Customer", "limit": 200})
    if isinstance(data, list):
        return data
    return data.get("items", [])


def list_suppliers(client: APIClient) -> list[dict[str, Any]]:
    """GET /api/v1/contacts?type=Supplier&limit=200.

    Returns:
        List of supplier contact dicts.
    """
    data = client.get("/api/v1/contacts", params={"type": "Supplier", "limit": 200})
    if isinstance(data, list):
        return data
    return data.get("items", [])
