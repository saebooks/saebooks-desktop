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

from saebooks_desktop.services.api_client import (
    APIClient,
    APIError,
    ServerOfflineError,
)


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

    Fallback path only — prefer reading ``bookkeeping_mode`` off the
    company record (see ``resolve_bookkeeping_mode``) so mode resolution
    doesn't cost a probe round-trip per render.
    """
    try:
        list_categories(client)
    except APIError as exc:
        if exc.status_code == 409:
            return False
        raise
    return True


def resolve_bookkeeping_mode(client: APIClient, company_id: str | None = None) -> str:
    """Resolve the active company's bookkeeping mode: ``"cashbook"`` or ``"full"``.

    Resolution order (adjudicated navigation verdict — nav branches on the
    company's ``bookkeeping_mode``, never on tier):

    1. The company record's ``bookkeeping_mode`` field
       (``GET /api/v1/companies/{id}``) — the app already holds/fetches
       the company object; this is the primary source.
    2. The 409 ``cashbook_not_configured`` probe (``is_cashbook_company``)
       — fallback only, for schema drift or a missing company id.
    3. ``"full"`` — default when the server is unreachable or both paths
       fail (full-mode nav degrades per-panel; cashbook panels would 409).
    """
    if company_id is None:
        from saebooks_desktop.services.settings import get_company_id

        company_id = get_company_id()

    if company_id:
        try:
            company = client.get(f"/api/v1/companies/{company_id}")
        except ServerOfflineError:
            # Server unreachable — the probe would fail too; don't burn a
            # second round-trip.
            return "full"
        except Exception:  # noqa: BLE001 — 404/schema drift → fallback probe
            company = None
        if isinstance(company, dict):
            mode = str(company.get("bookkeeping_mode") or "").strip().lower()
            if mode in ("cashbook", "full"):
                return mode

    try:
        return "cashbook" if is_cashbook_company(client) else "full"
    except Exception:  # noqa: BLE001 — offline etc.
        return "full"


def set_bookkeeping_mode(
    client: APIClient,
    company_id: str,
    mode: str,
    bank_account_id: str | None = None,
) -> dict[str, Any]:
    """Flip the company between cashbook and full bookkeeping modes.

    ``POST /api/v1/companies/{id}/bookkeeping-mode`` with
    ``{"mode": "cashbook"|"full"}``. The engine picks the direction:

    * ``mode="full"`` → ``upgrade_cashbook_to_full`` — lossless; cashbook
      entries already are real journal entries.
    * ``mode="cashbook"`` → ``downgrade_full_to_cashbook`` — engine-gated
      on zero open AR (422 with the offending invoices in the message).
      ``bank_account_id`` is required by the engine only when the company
      has no pre-existing ``cashbook_default_bank_account_id``.

    Idempotent: same-mode calls return current state with a 200.

    Raises:
        ServerOfflineError: if the server is unreachable.
        APIError: 422 on engine refusal — ``str(exc)`` carries the
            engine's error message; surface it to the user verbatim.
    """
    if mode not in ("cashbook", "full"):
        raise ValueError(f"Invalid bookkeeping mode: {mode!r}")
    body: dict[str, Any] = {"mode": mode}
    if bank_account_id:
        body["bank_account_id"] = bank_account_id
    return client.post(f"/api/v1/companies/{company_id}/bookkeeping-mode", json=body)
