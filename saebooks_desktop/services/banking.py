"""Banking service wrapper — thin helper over APIClient.get().

Provides access to bank statement lines (BSLs) awaiting reconciliation.
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient

_VALID_BSL_STATUSES = {"unmatched", "matched", "ignored"}


def list_bank_statement_lines(
    client: APIClient,
    account_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
    status_filter: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """Return a page of bank statement lines from ``GET /api/v1/bank-statement-lines``.

    Args:
        client: Caller-supplied APIClient instance.
        account_id: Filter to a specific bank account (optional).
        page: 1-based page number.
        page_size: Items per page.
        status_filter: One of ``"unmatched"``, ``"matched"``, ``"ignored"``
            or ``None`` / ``""`` to return all statuses.
        date_from: ISO-8601 date string (inclusive lower bound on date).
        date_to: ISO-8601 date string (inclusive upper bound on date).

    Returns:
        List of bank statement line dicts (may be empty).
    """
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if account_id:
        params["account_id"] = account_id
    if status_filter and status_filter.lower() in _VALID_BSL_STATUSES:
        params["status"] = status_filter.lower()
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to

    data = client.get("/api/v1/bank-statement-lines", params=params)
    return data.get("items", [])
