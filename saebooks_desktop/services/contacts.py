"""Contacts service wrapper — thin helper over APIClient.get().

Constructs query params and returns the ``items`` list from the paginated
response.  Callers should catch ``ServerOfflineError`` and ``APIError`` from
``api_client`` if they want custom error handling.
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def list_contacts(
    client: APIClient,
    page: int = 1,
    page_size: int = 50,
    type_filter: str | None = None,
    search_query: str | None = None,
) -> list[dict[str, Any]]:
    """Return a page of contacts from ``GET /api/v1/contacts``.

    Args:
        client: Caller-supplied APIClient instance.
        page: 1-based page number.
        page_size: Items per page.
        type_filter: One of ``"customer"``, ``"supplier"``, ``"employee"``,
            ``"other"`` or ``None`` / ``""`` to return all types.
        search_query: Free-text search string applied server-side (name/email).

    Returns:
        List of contact dicts (may be empty).
    """
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if type_filter:
        params["type"] = type_filter.lower()
    if search_query:
        params["q"] = search_query

    data = client.get("/api/v1/contacts", params=params)
    return data.get("items", [])
