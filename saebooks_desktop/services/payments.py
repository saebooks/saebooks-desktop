"""Payments service wrapper — thin helper over APIClient.get().

Covers both payments received (from customers) and payments made (to suppliers).
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient

_VALID_DIRECTIONS = {"in", "out"}


def list_payments(
    client: APIClient,
    page: int = 1,
    page_size: int = 50,
    direction_filter: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """Return a page of payments from ``GET /api/v1/payments``.

    Args:
        client: Caller-supplied APIClient instance.
        page: 1-based page number.
        page_size: Items per page.
        direction_filter: One of ``"in"`` (received), ``"out"`` (made),
            or ``None`` / ``""`` to return all.
        date_from: ISO-8601 date string (inclusive lower bound on date).
        date_to: ISO-8601 date string (inclusive upper bound on date).

    Returns:
        List of payment dicts (may be empty).
    """
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if direction_filter and direction_filter.lower() in _VALID_DIRECTIONS:
        params["direction"] = direction_filter.lower()
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to

    data = client.get("/api/v1/payments", params=params)
    return data.get("items", [])
