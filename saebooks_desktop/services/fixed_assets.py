"""Fixed assets service — thin wrappers over APIClient.

Each function constructs the query params / payload and calls the
appropriate REST verb.  Callers should catch ``ServerOfflineError``
and ``APIError`` from ``api_client`` if they want custom error handling.
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def list_fixed_assets(
    client: APIClient,
    page: int = 1,
    page_size: int = 50,
    status_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Return a page of fixed assets from ``GET /api/v1/fixed_assets``.

    Args:
        client: Caller-supplied APIClient instance.
        page: 1-based page number.
        page_size: Items per page.
        status_filter: One of ``"active"``, ``"disposed"`` or ``None`` / ``""``
            to return all statuses.

    Returns:
        List of fixed asset dicts (may be empty).
    """
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if status_filter:
        params["status"] = status_filter.lower()

    data = client.get("/api/v1/fixed_assets", params=params)
    return data.get("items", [])


def get_fixed_asset(client: APIClient, asset_id: str) -> dict[str, Any]:
    """Fetch a single fixed asset by id.

    Args:
        client: Caller-supplied APIClient instance.
        asset_id: Asset UUID string.

    Returns:
        Asset dict including a ``depreciation_runs`` list.

    Raises:
        ServerOfflineError: If the server cannot be reached.
        APIError: On non-2xx response.
    """
    return client.get(f"/api/v1/fixed_assets/{asset_id}")


def create_fixed_asset(client: APIClient, data: dict[str, Any]) -> dict[str, Any]:
    """POST /api/v1/fixed_assets — create a new fixed asset.

    Args:
        client: Caller-supplied APIClient.
        data: Asset payload dict (name, code, purchase_date, purchase_price, …).

    Returns:
        Created asset dict from API.

    Raises:
        ServerOfflineError: If the server is unreachable.
        APIError: On non-2xx response.
    """
    return client.post("/api/v1/fixed_assets", json=data)


def update_fixed_asset(
    client: APIClient, asset_id: str, data: dict[str, Any]
) -> tuple[int, dict[str, Any]]:
    """PATCH /api/v1/fixed_assets/{asset_id}.

    Args:
        client: Caller-supplied APIClient.
        asset_id: Asset UUID string.
        data: Partial asset payload.

    Returns:
        (status_code, asset_dict) — 200 on success, 409 on conflict.

    Raises:
        ServerOfflineError: If the server is unreachable.
        APIError: On non-2xx/non-409 response.
    """
    return client.patch(f"/api/v1/fixed_assets/{asset_id}", json=data)


def archive_fixed_asset(client: APIClient, asset_id: str) -> dict[str, Any]:
    """DELETE /api/v1/fixed_assets/{asset_id} — archive the asset.

    Args:
        client: Caller-supplied APIClient.
        asset_id: Asset UUID string.

    Returns:
        Response dict from API.

    Raises:
        ServerOfflineError: If the server is unreachable.
        APIError: On non-2xx response.
    """
    return client.post(f"/api/v1/fixed_assets/{asset_id}/archive")


def run_depreciation(
    client: APIClient, asset_id: str, data: dict[str, Any] | None = None
) -> dict[str, Any]:
    """POST /api/v1/fixed_assets/{asset_id}/depreciate — run a depreciation period.

    Args:
        client: Caller-supplied APIClient.
        asset_id: Asset UUID string.
        data: Optional depreciation payload (period_date, etc.).

    Returns:
        Updated asset dict including the new depreciation run.

    Raises:
        ServerOfflineError: If the server is unreachable.
        APIError: On non-2xx response.
    """
    return client.post(f"/api/v1/fixed_assets/{asset_id}/depreciate", json=data or {})


def dispose_asset(
    client: APIClient, asset_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    """POST /api/v1/fixed_assets/{asset_id}/dispose — dispose of an asset.

    Args:
        client: Caller-supplied APIClient.
        asset_id: Asset UUID string.
        data: Disposal payload (disposal_type, disposal_date, sale_price, …).

    Returns:
        Updated asset dict.

    Raises:
        ServerOfflineError: If the server is unreachable.
        APIError: On non-2xx response.
    """
    return client.post(f"/api/v1/fixed_assets/{asset_id}/dispose", json=data)
