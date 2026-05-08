"""Proration service helpers — call the three preview endpoints."""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def preview(
    client: APIClient,
    full_period_amount: str,
    basis: str,
    service_start: str,
    service_end: str,
) -> dict[str, Any]:
    """POST /api/v1/proration/preview — Prorate #3 generic per-line."""
    return client.post(
        "/api/v1/proration/preview",
        json={
            "full_period_amount": full_period_amount,
            "basis": basis.upper(),
            "service_start": service_start,
            "service_end": service_end,
        },
    )


def first_period_preview(
    client: APIClient,
    full_period_amount: str,
    basis: str,
    service_start: str,
    service_end: str,
) -> dict[str, Any]:
    """POST /api/v1/proration/first-period-preview — Prorate #1."""
    return client.post(
        "/api/v1/proration/first-period-preview",
        json={
            "full_period_amount": full_period_amount,
            "basis": basis.upper(),
            "service_start": service_start,
            "service_end": service_end,
        },
    )


def plan_change_preview(
    client: APIClient,
    old_period_amount: str,
    new_period_amount: str,
    period_start: str,
    period_end: str,
    change_date: str,
) -> dict[str, Any]:
    """POST /api/v1/proration/plan-change-preview — Prorate #2."""
    return client.post(
        "/api/v1/proration/plan-change-preview",
        json={
            "old_period_amount": old_period_amount,
            "new_period_amount": new_period_amount,
            "period_start": period_start,
            "period_end": period_end,
            "change_date": change_date,
        },
    )
