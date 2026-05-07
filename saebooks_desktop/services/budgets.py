"""Budgets service wrapper — thin helper over APIClient.get() and post().

Covers listing budgets and creating new ones.  Callers should catch
``ServerOfflineError`` and ``APIError`` from ``api_client`` if they want
custom error handling.
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def list_budgets(
    client: APIClient,
    page: int = 1,
    page_size: int = 50,
    status_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Return a page of budgets from ``GET /api/v1/budgets``.

    Args:
        client: Caller-supplied APIClient instance.
        page: 1-based page number.
        page_size: Items per page.
        status_filter: One of ``"active"``, ``"closed"`` or ``None`` / ``""``
            to return all statuses.

    Returns:
        List of budget dicts (may be empty).
    """
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if status_filter:
        params["status"] = status_filter.lower()

    data = client.get("/api/v1/budgets", params=params)
    return data.get("items", [])


def create_budget(
    client: APIClient,
    name: str,
    fiscal_year: str,
) -> dict[str, Any]:
    """Create a new budget via ``POST /api/v1/budgets``.

    Args:
        client: Caller-supplied APIClient instance.
        name: Budget name.
        fiscal_year: Fiscal year string (e.g. ``"2024-25"``).

    Returns:
        The created budget dict returned by the API.
    """
    payload: dict[str, Any] = {
        "name": name,
        "fiscal_year": fiscal_year,
        "lines": [],
    }
    return client.post("/api/v1/budgets", json=payload)
