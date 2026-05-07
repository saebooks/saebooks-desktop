"""Accounts service wrapper — thin helper over APIClient.get().

Returns the full chart of accounts in one call.  The AU seed has ~80-120
accounts; loading all at once is intentional (no pagination for the CoA).
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def list_accounts(client: APIClient) -> list[dict[str, Any]]:
    """Return the full chart of accounts from ``GET /api/v1/accounts``.

    Args:
        client: Caller-supplied APIClient instance.

    Returns:
        List of account dicts (may be empty).  Each dict is expected to
        contain at minimum: ``id``, ``code``, ``name``, ``type``,
        ``balance``.
    """
    data = client.get("/api/v1/accounts")
    # Support both a top-level list and a paginated-style {"items": [...]}
    if isinstance(data, list):
        return data
    return data.get("items", [])
