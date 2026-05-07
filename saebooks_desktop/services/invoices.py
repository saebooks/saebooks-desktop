"""Invoice and Bill service wrappers — thin helpers over APIClient.get().

Each function constructs the query params and returns the ``items`` list from
the paginated response.  Callers should catch ``ServerOfflineError`` and
``APIError`` from ``api_client`` if they want custom error handling.
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def list_invoices(
    client: APIClient,
    page: int = 1,
    page_size: int = 50,
    status_filter: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """Return a page of invoices from ``GET /api/v1/invoices``.

    Args:
        client: Caller-supplied APIClient instance.
        page: 1-based page number.
        page_size: Items per page.
        status_filter: One of ``"draft"``, ``"posted"``, ``"voided"`` or
            ``None`` / ``""`` to return all statuses.
        date_from: ISO-8601 date string (inclusive lower bound on issue_date).
        date_to: ISO-8601 date string (inclusive upper bound on issue_date).

    Returns:
        List of invoice dicts (may be empty).
    """
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if status_filter:
        params["status"] = status_filter.lower()
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to

    data = client.get("/api/v1/invoices", params=params)
    return data.get("items", [])


def list_bills(
    client: APIClient,
    page: int = 1,
    page_size: int = 50,
    status_filter: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """Return a page of bills from ``GET /api/v1/bills``.

    Args:
        client: Caller-supplied APIClient instance.
        page: 1-based page number.
        page_size: Items per page.
        status_filter: One of ``"draft"``, ``"posted"``, ``"voided"`` or
            ``None`` / ``""`` to return all statuses.
        date_from: ISO-8601 date string (inclusive lower bound on bill_date).
        date_to: ISO-8601 date string (inclusive upper bound on bill_date).

    Returns:
        List of bill dicts (may be empty).
    """
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if status_filter:
        params["status"] = status_filter.lower()
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to

    data = client.get("/api/v1/bills", params=params)
    return data.get("items", [])
