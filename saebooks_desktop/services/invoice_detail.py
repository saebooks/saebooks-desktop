"""Invoice detail service — fetches a single invoice with lines.

Returns a raw dict from ``GET /api/v1/invoices/{invoice_id}``.
Callers should catch ``ServerOfflineError`` and ``APIError`` from
``api_client`` if they want custom error handling.
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def get_invoice(client: APIClient, invoice_id: str) -> dict[str, Any]:
    """Fetch a single invoice by id.

    Args:
        client: Caller-supplied APIClient instance.
        invoice_id: Invoice UUID string.

    Returns:
        Invoice dict including a ``lines`` list.

    Raises:
        ServerOfflineError: If the server cannot be reached.
        APIError: On non-2xx response.
    """
    return client.get(f"/api/v1/invoices/{invoice_id}")
