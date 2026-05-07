"""Journal templates service — thin wrappers over APIClient.

Functions:
    list_journal_templates(client)         → list[dict]  — GET /api/v1/journal_templates
    create_journal_template(client, data)  → dict         — POST /api/v1/journal_templates
    get_journal_template(client, id)       → dict         — GET /api/v1/journal_templates/{id}
    delete_journal_template(client, id)    → int          — DELETE /api/v1/journal_templates/{id}
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def list_journal_templates(client: APIClient) -> list[dict[str, Any]]:
    """Return all journal templates from ``GET /api/v1/journal_templates``.

    Args:
        client: Caller-supplied APIClient instance.

    Returns:
        List of journal template dicts (may be empty).
    """
    data = client.get("/api/v1/journal_templates")
    if isinstance(data, list):
        return data
    return data.get("items", [])


def create_journal_template(
    client: APIClient, data: dict[str, Any]
) -> dict[str, Any]:
    """Create a journal template via ``POST /api/v1/journal_templates``.

    Args:
        client: Caller-supplied APIClient instance.
        data: Payload dict with keys: name, description.

    Returns:
        The created journal template dict.
    """
    return client.post("/api/v1/journal_templates", json=data)


def get_journal_template(
    client: APIClient, template_id: str
) -> dict[str, Any]:
    """Fetch a single journal template from ``GET /api/v1/journal_templates/{id}``.

    Args:
        client: Caller-supplied APIClient instance.
        template_id: The template's id.

    Returns:
        The journal template dict.
    """
    return client.get(f"/api/v1/journal_templates/{template_id}")


def delete_journal_template(client: APIClient, template_id: str) -> int:
    """Delete a journal template via ``DELETE /api/v1/journal_templates/{id}``.

    Args:
        client: Caller-supplied APIClient instance.
        template_id: The template's id.

    Returns:
        HTTP status code.
    """
    return client.delete(f"/api/v1/journal_templates/{template_id}")
