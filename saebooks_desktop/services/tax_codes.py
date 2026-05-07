"""Tax codes service — thin wrappers over APIClient.

Note: ``list_tax_codes`` also exists in ``company_settings.py`` (used by the
Settings view).  This module is the canonical home for the full CRUD surface
used by the standalone TaxCodesView.

Functions:
    list_tax_codes(client)            → list[dict]  — GET /api/v1/tax_codes
    create_tax_code(client, data)     → dict         — POST /api/v1/tax_codes
    patch_tax_code(client, id, data)  → dict         — PATCH /api/v1/tax_codes/{id}
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def list_tax_codes(client: APIClient) -> list[dict[str, Any]]:
    """Return all tax codes from ``GET /api/v1/tax_codes``.

    Args:
        client: Caller-supplied APIClient instance.

    Returns:
        List of tax code dicts (may be empty).
    """
    data = client.get("/api/v1/tax_codes")
    if isinstance(data, list):
        return data
    return data.get("items", [])


def create_tax_code(
    client: APIClient, data: dict[str, Any]
) -> dict[str, Any]:
    """Create a tax code via ``POST /api/v1/tax_codes``.

    Args:
        client: Caller-supplied APIClient instance.
        data: Payload dict with keys: code, name, rate, tax_type.

    Returns:
        The created tax code dict.
    """
    return client.post("/api/v1/tax_codes", json=data)


def patch_tax_code(
    client: APIClient, code_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Patch a tax code via ``PATCH /api/v1/tax_codes/{id}``.

    Args:
        client: Caller-supplied APIClient instance.
        code_id: The tax code's id.
        data: Partial payload dict.

    Returns:
        The updated tax code dict.
    """
    _status, result = client.patch(f"/api/v1/tax_codes/{code_id}", json=data)
    return result
