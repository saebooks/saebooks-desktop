"""Thin REST wrappers for /api/v1/cashbook.

Cashbook is the engine's simplified single-bank-account bookkeeping mode
(``company.bookkeeping_mode == "cashbook"``). A full-mode company answers
these endpoints with a 409 ``cashbook_not_configured`` — see
``is_cashbook_company``.

Field names on the wire follow ``CashbookEntryCreate`` /
``CashbookEntryOut`` exactly (``entry_date``, ``category_code``,
``direction`` of ``"income"``/``"expense"``, ``amount`` sent as a string) —
see the engine OpenAPI schema, not the shorter names a caller might expect.
"""
from __future__ import annotations

import uuid
from typing import Any

from saebooks_desktop.services.api_client import APIClient, APIError


def list_entries(
    client: APIClient,
    direction: str | None = None,
    category: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return a page of cashbook entries from ``GET /api/v1/cashbook/entries``."""
    params: dict[str, Any] = {"limit": limit}
    if direction:
        params["direction"] = direction
    if category:
        params["category"] = category
    if date_from:
        params["from"] = date_from
    if date_to:
        params["to"] = date_to

    data = client.get("/api/v1/cashbook/entries", params=params)
    return data.get("items", [])


def get_entry(client: APIClient, entry_id: str) -> dict[str, Any]:
    """Return one cashbook entry from ``GET /api/v1/cashbook/entries/{id}``."""
    return client.get(f"/api/v1/cashbook/entries/{entry_id}")


def create_entry(client: APIClient, data: dict[str, Any]) -> dict[str, Any]:
    """Record a cashbook entry via ``POST /api/v1/cashbook/entries``.

    Attaches a fresh ``X-Idempotency-Key`` (a uuid4 hex string) to every
    call — the engine uses it to de-dupe retried requests.

    Args:
        client: Caller-supplied APIClient instance.
        data: Body matching ``CashbookEntryCreate`` — ``entry_date``,
            ``amount``, ``direction`` (``"income"`` or ``"expense"``) and
            ``category_code`` are required; ``description`` and
            ``gst_amount`` are optional.

    Returns:
        The created ``CashbookEntryOut`` dict.
    """
    return client.post(
        "/api/v1/cashbook/entries",
        json=data,
        headers={"X-Idempotency-Key": uuid.uuid4().hex},
    )


def delete_entry(client: APIClient, entry_id: str) -> int:
    """Soft-delete (reverse) a cashbook entry via ``DELETE .../{id}``.

    Returns the HTTP status code (204 on success, idempotent on repeat).
    """
    return client.delete(f"/api/v1/cashbook/entries/{entry_id}")


def list_categories(client: APIClient) -> list[dict[str, Any]]:
    """Return the cashbook category list from ``GET /api/v1/cashbook/categories``."""
    return client.get("/api/v1/cashbook/categories")


def get_summary(
    client: APIClient,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Return the P&L-shaped summary from ``GET /api/v1/cashbook/summary``.

    ``from``/``to`` are required by the engine. When the caller doesn't
    supply a range, defaults to calendar-year-to-date (jurisdiction-neutral
    — the engine's own AU/EE modules apply their own financial-year
    conventions elsewhere).
    """
    if date_from is None or date_to is None:
        import datetime

        today = datetime.date.today()
        date_from = date_from or today.replace(month=1, day=1).isoformat()
        date_to = date_to or today.isoformat()

    return client.get(
        "/api/v1/cashbook/summary", params={"from": date_from, "to": date_to}
    )


def is_cashbook_company(client: APIClient) -> bool:
    """Return True if the active company is in cashbook bookkeeping mode.

    A full-mode company answers the cashbook endpoints with a 409
    ``cashbook_not_configured``; probe with ``list_categories`` (cheapest,
    no query params) and interpret the result.
    """
    try:
        list_categories(client)
    except APIError as exc:
        if exc.status_code == 409:
            return False
        raise
    return True
