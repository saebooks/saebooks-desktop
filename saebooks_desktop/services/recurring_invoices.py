"""Recurring invoices service wrapper — thin helper over APIClient.

Covers listing recurring invoices and triggering a manual run.  Callers
should catch ``ServerOfflineError`` and ``APIError`` from ``api_client``
if they want custom error handling.
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def list_recurring_invoices(
    client: APIClient,
    page: int = 1,
    page_size: int = 50,
    status_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Return a page of recurring invoices from ``GET /api/v1/recurring_invoices``.

    Args:
        client: Caller-supplied APIClient instance.
        page: 1-based page number.
        page_size: Items per page.
        status_filter: One of ``"active"``, ``"paused"``, ``"ended"`` or
            ``None`` / ``""`` to return all statuses.

    Returns:
        List of recurring invoice dicts (may be empty).
    """
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if status_filter:
        params["status"] = status_filter.lower()

    data = client.get("/api/v1/recurring_invoices", params=params)
    return data.get("items", [])


def run_recurring_invoice(
    client: APIClient,
    recurring_invoice_id: str,
) -> dict[str, Any]:
    """Trigger the next invoice generation via ``POST /api/v1/recurring_invoices/{id}/run``.

    Args:
        client: Caller-supplied APIClient instance.
        recurring_invoice_id: The id of the recurring invoice template to run.

    Returns:
        The generated invoice dict returned by the API.
    """
    return client.post(
        f"/api/v1/recurring_invoices/{recurring_invoice_id}/run", json={}
    )
