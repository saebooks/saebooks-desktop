"""Purchase-order service helpers — thin wrappers over APIClient."""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def list_purchase_orders(
    client: APIClient,
    page: int = 1,
    page_size: int = 50,
    status_filter: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """Return a page of purchase orders from ``GET /api/v1/purchase_orders``.

    ``status_filter`` is one of ``DRAFT/OPEN/PARTIAL/RECEIVED/CLOSED/CANCELLED``
    (case-insensitive, sent upper-cased) or ``None`` for all.
    """
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if status_filter:
        params["status"] = status_filter.upper()
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to

    data = client.get("/api/v1/purchase_orders", params=params)
    return data.get("items", [])


def get_purchase_order(client: APIClient, po_id: str) -> dict[str, Any]:
    """Fetch a single purchase order with its lines."""
    return client.get(f"/api/v1/purchase_orders/{po_id}")
