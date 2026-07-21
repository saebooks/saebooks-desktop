"""Reconciliation service wrapper — thin helpers over APIClient.

Wraps the engine's ``/api/v1/reconciliation`` surface: the reconcilable
account list, unmatched bank statement lines for an account, suggested
matching journal entries, and the match / unmatch / auto-match operations.

Every helper takes a caller-supplied ``APIClient`` and returns plain
dicts/lists so the views stay transport-agnostic and offscreen-testable.
Money is always carried as strings (the engine emits Decimals as strings);
never coerce to float.
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def list_reconcilable_accounts(client: APIClient) -> list[dict[str, Any]]:
    """Bank/cash accounts eligible for reconciliation.

    ``GET /api/v1/reconciliation/accounts`` → bare list of
    ``{id, code, name}``. These are the CHART accounts a bank statement
    line's ``account_id`` must reference — the same set the import picker
    must offer, so import and reconcile agree on account identity.
    """
    data = client.get("/api/v1/reconciliation/accounts")
    return data if isinstance(data, list) else data.get("items", [])


def list_unmatched(client: APIClient, account_id: str) -> list[dict[str, Any]]:
    """Unmatched bank statement lines for one account.

    ``GET /api/v1/reconciliation/unmatched?account_id=X`` → bare list of
    BSL dicts (id, account_id, txn_date, description, amount, reference,
    status, …).
    """
    data = client.get(
        "/api/v1/reconciliation/unmatched", params={"account_id": account_id}
    )
    return data if isinstance(data, list) else data.get("items", [])


def suggest_matches(client: APIClient, bsl_id: str) -> list[dict[str, Any]]:
    """Candidate posted journal entries that could match a BSL.

    ``GET /api/v1/reconciliation/suggest/{bsl_id}`` → list of entry dicts
    (id, ref, entry_date, description, status, and — on newer engines —
    confidence / match_reason / rule_id).
    """
    data = client.get(f"/api/v1/reconciliation/suggest/{bsl_id}")
    return data if isinstance(data, list) else data.get("items", [])


def match(client: APIClient, bsl_id: str, entry_id: str) -> dict[str, Any]:
    """Match a BSL to a posted journal entry.

    ``POST /api/v1/reconciliation/match`` body ``{bsl_id, entry_id}``.
    Returns the updated BSL dict.
    """
    return client.post(
        "/api/v1/reconciliation/match",
        json={"bsl_id": bsl_id, "entry_id": entry_id},
    )


def unmatch(client: APIClient, bsl_id: str) -> dict[str, Any]:
    """Clear a BSL's match, returning it to UNMATCHED.

    ``POST /api/v1/reconciliation/unmatch/{bsl_id}`` (no body).
    """
    return client.post(f"/api/v1/reconciliation/unmatch/{bsl_id}")


def auto_match(client: APIClient, account_id: str) -> dict[str, Any]:
    """Run honest auto-matching for all unmatched BSLs in an account.

    ``POST /api/v1/reconciliation/auto_match?account_id=X`` →
    ``{matched, skipped_ambiguous, skipped_no_candidate}`` (older engines
    return just ``{matched}``). Links a line only when exactly one
    candidate scores HIGH confidence; never posts anything.
    """
    return client.post(
        f"/api/v1/reconciliation/auto_match?account_id={account_id}"
    )
