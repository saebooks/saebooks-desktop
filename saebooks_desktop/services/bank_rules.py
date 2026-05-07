"""Bank rules service — thin wrappers over APIClient.

Functions:
    list_bank_rules(client)            → list[dict]  — GET /api/v1/bank_rules
    create_bank_rule(client, data)     → dict         — POST /api/v1/bank_rules
    patch_bank_rule(client, id, data)  → dict         — PATCH /api/v1/bank_rules/{id}
    delete_bank_rule(client, id)       → int          — DELETE /api/v1/bank_rules/{id}
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def list_bank_rules(client: APIClient) -> list[dict[str, Any]]:
    """Return all bank rules from ``GET /api/v1/bank_rules``.

    Args:
        client: Caller-supplied APIClient instance.

    Returns:
        List of bank rule dicts (may be empty).
    """
    data = client.get("/api/v1/bank_rules")
    if isinstance(data, list):
        return data
    return data.get("items", [])


def create_bank_rule(
    client: APIClient, data: dict[str, Any]
) -> dict[str, Any]:
    """Create a bank rule via ``POST /api/v1/bank_rules``.

    Args:
        client: Caller-supplied APIClient instance.
        data: Payload dict with keys: name, match_description, account_id,
            auto_apply.

    Returns:
        The created bank rule dict.
    """
    return client.post("/api/v1/bank_rules", json=data)


def patch_bank_rule(
    client: APIClient, rule_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Patch a bank rule via ``PATCH /api/v1/bank_rules/{id}``.

    Args:
        client: Caller-supplied APIClient instance.
        rule_id: The bank rule's id.
        data: Partial payload dict.

    Returns:
        The updated bank rule dict.
    """
    _status, result = client.patch(f"/api/v1/bank_rules/{rule_id}", json=data)
    return result


def delete_bank_rule(client: APIClient, rule_id: str) -> int:
    """Delete a bank rule via ``DELETE /api/v1/bank_rules/{id}``.

    Args:
        client: Caller-supplied APIClient instance.
        rule_id: The bank rule's id.

    Returns:
        HTTP status code.
    """
    return client.delete(f"/api/v1/bank_rules/{rule_id}")
