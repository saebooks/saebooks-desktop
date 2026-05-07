"""Projects service wrapper — thin helper over APIClient.get() and post().

Covers listing projects and creating new ones.  Callers should catch
``ServerOfflineError`` and ``APIError`` from ``api_client`` if they want
custom error handling.
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def list_projects(
    client: APIClient,
    page: int = 1,
    page_size: int = 50,
    status_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Return a page of projects from ``GET /api/v1/projects``.

    Args:
        client: Caller-supplied APIClient instance.
        page: 1-based page number.
        page_size: Items per page.
        status_filter: One of ``"active"``, ``"closed"`` or ``None`` / ``""``
            to return all statuses.

    Returns:
        List of project dicts (may be empty).
    """
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if status_filter:
        params["status"] = status_filter.lower()

    data = client.get("/api/v1/projects", params=params)
    return data.get("items", [])


def create_project(
    client: APIClient,
    name: str,
    code: str,
    budget: str = "",
    contact_id: str | None = None,
) -> dict[str, Any]:
    """Create a new project via ``POST /api/v1/projects``.

    Args:
        client: Caller-supplied APIClient instance.
        name: Project name.
        code: Unique project code.
        budget: Budget amount as string (e.g. ``"5000.00"``).
        contact_id: Optional associated contact id.

    Returns:
        The created project dict returned by the API.
    """
    payload: dict[str, Any] = {"name": name, "code": code}
    if budget:
        payload["budget"] = budget
    if contact_id:
        payload["contact_id"] = contact_id

    return client.post("/api/v1/projects", json=payload)
