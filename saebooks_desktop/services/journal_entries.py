"""Journal entries service wrapper — thin helper over APIClient.get().

Each function constructs query params and returns the ``items`` list from
the paginated response.  Callers should catch ``ServerOfflineError`` and
``APIError`` from ``api_client`` if they want custom error handling.
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient

_VALID_SOURCES = {"manual", "invoice", "bill", "payment", "reconciliation"}


def list_journal_entries(
    client: APIClient,
    page: int = 1,
    page_size: int = 50,
    date_from: str | None = None,
    date_to: str | None = None,
    source_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Return a page of journal entries from ``GET /api/v1/journal-entries``.

    Args:
        client: Caller-supplied APIClient instance.
        page: 1-based page number.
        page_size: Items per page.
        date_from: ISO-8601 date string (inclusive lower bound on date).
        date_to: ISO-8601 date string (inclusive upper bound on date).
        source_filter: One of ``"manual"``, ``"invoice"``, ``"bill"``,
            ``"payment"``, ``"reconciliation"`` or ``None`` / ``""`` to
            return all sources.

    Returns:
        List of journal entry dicts (may be empty).
    """
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    if source_filter and source_filter.lower() in _VALID_SOURCES:
        params["source"] = source_filter.lower()

    data = client.get("/api/v1/journal-entries", params=params)
    return data.get("items", [])
