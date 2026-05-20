"""Thin REST wrappers for /api/v1/expenses.

Mirror of the bill helpers in ``services/invoices.py``. Each function
returns the parsed JSON response and lets the caller deal with
APIClient exceptions (offline, auth) directly.
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def list_expenses(
    client: APIClient,
    page: int = 1,
    page_size: int = 50,
    status_filter: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """Return a page of expenses from ``GET /api/v1/expenses``."""
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if status_filter:
        params["status"] = status_filter.upper()
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to

    data = client.get("/api/v1/expenses", params=params)
    return data.get("items", [])


def get_expense(client: APIClient, expense_id: str) -> dict[str, Any]:
    """Return one expense (with lines) from ``GET /api/v1/expenses/{id}``."""
    return client.get(f"/api/v1/expenses/{expense_id}")


def post_expense(
    client: APIClient, expense_id: str, version: int
) -> dict[str, Any]:
    """Transition DRAFT → POSTED."""
    return client.post(
        f"/api/v1/expenses/{expense_id}/post",
        headers={"If-Match": str(version)},
    )


def void_expense(
    client: APIClient, expense_id: str, version: int
) -> dict[str, Any]:
    """Transition any non-VOIDED → VOIDED (reverses JE if POSTED)."""
    return client.post(
        f"/api/v1/expenses/{expense_id}/void",
        headers={"If-Match": str(version)},
    )
