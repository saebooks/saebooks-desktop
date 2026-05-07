"""Bill detail service — fetches a single bill with lines.

Returns a raw dict from ``GET /api/v1/bills/{bill_id}``.
Callers should catch ``ServerOfflineError`` and ``APIError`` from
``api_client`` if they want custom error handling.
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def get_bill(client: APIClient, bill_id: str) -> dict[str, Any]:
    """Fetch a single bill by id.

    Args:
        client: Caller-supplied APIClient instance.
        bill_id: Bill UUID string.

    Returns:
        Bill dict including a ``lines`` list.

    Raises:
        ServerOfflineError: If the server cannot be reached.
        APIError: On non-2xx response.
    """
    return client.get(f"/api/v1/bills/{bill_id}")
