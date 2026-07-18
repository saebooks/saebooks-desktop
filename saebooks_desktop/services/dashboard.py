"""Dashboard service wrappers — composes reports + module health into one model.

Each ``fetch_*`` function is a thin wrapper over ``APIClient.get()``, mirroring
the pattern in ``services/reports.py``.  ``build_dashboard_model`` composes
them defensively: each section is fetched independently so a single degraded
module (``ModuleUnavailableError``) or report failure (``APIError``) doesn't
blank the whole dashboard — only ``ServerOfflineError`` (server unreachable)
propagates, since in that case nothing on the dashboard can be shown anyway.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from saebooks_desktop.services.api_client import (
    APIClient,
    APIError,
    ModuleUnavailableError,
    ServerOfflineError,
)


def fetch_profit_loss_summary(
    client: APIClient, from_date: str, to_date: str
) -> dict[str, Any]:
    """Fetch the P&L for [*from_date*, *to_date*] (ISO-8601 strings).

    Returns the full response dict from ``GET /api/v1/reports/profit_loss``.
    See ``services.reports.get_profit_loss`` for the expected shape.
    """
    return client.get(
        "/api/v1/reports/profit_loss",
        params={"from_date": from_date, "to_date": to_date},
    )


def fetch_aged_receivables_total(client: APIClient, as_of_date: str) -> dict[str, Any]:
    """Fetch the aged receivables report as of *as_of_date* (ISO-8601 string).

    Returns the full response dict from ``GET /api/v1/reports/aged_receivables``.
    See ``services.reports.get_aged_receivables`` for the expected shape.
    """
    return client.get(
        "/api/v1/reports/aged_receivables", params={"as_of_date": as_of_date}
    )


def fetch_aged_payables_total(client: APIClient, as_of_date: str) -> dict[str, Any]:
    """Fetch the aged payables report as of *as_of_date* (ISO-8601 string).

    Returns the full response dict from ``GET /api/v1/reports/aged_payables``.
    Response shape is identical to ``fetch_aged_receivables_total`` but
    covers bills/payables.
    """
    return client.get(
        "/api/v1/reports/aged_payables", params={"as_of_date": as_of_date}
    )


def fetch_module_health(client: APIClient) -> dict[str, Any]:
    """Fetch module entitlement/health from ``GET /api/v1/modules/usage``.

    Expected shape::

        {
            "edition": "...",
            "effective_edition": "...",
            "bookkeeping_mode": "...",
            "modules": [
                {"id": "capture", "kind": "delegated", "entitled": true, "health": "ok"},
                ...
            ],
            "caps": {...},
        }

    # TODO: endpoint /api/v1/modules/usage must exist on the server.
    """
    return client.get("/api/v1/modules/usage")


def _trailing_12_month_start(today: str) -> str:
    """Return the ISO date exactly one year before *today* (same month/day).

    Used as the P&L ``from_date`` for a trailing-12-month window ending
    *today*.  ``today`` is an ISO-8601 date string (``YYYY-MM-DD``).
    """
    d = datetime.strptime(today, "%Y-%m-%d").date()
    try:
        start = d.replace(year=d.year - 1)
    except ValueError:
        # Feb-29 on a non-leap prior year — fall back to Feb-28.
        start = d.replace(year=d.year - 1, day=28)
    return start.isoformat()


def build_dashboard_model(client: APIClient, today: str) -> dict[str, Any]:
    """Compose the dashboard's data sections from independent report fetches.

    Args:
        client: Caller-supplied APIClient instance.
        today: ISO-8601 date string (``YYYY-MM-DD``) used as "as of" for the
            aged reports and as the end of the trailing-12-month P&L window.

    Returns:
        ``{"pl": dict | None, "ar": dict | None, "ap": dict | None,
        "modules": dict | None, "errors": {section: message}}``.

        Each section is fetched independently inside its own try/except: a
        ``ModuleUnavailableError`` or ``APIError`` for that section is
        recorded in ``errors[section]`` and the section value is ``None``,
        but the remaining sections are still attempted.

    Raises:
        ServerOfflineError: if the server itself is unreachable — in that
            case the whole dashboard is offline and nothing is composed.
    """
    from_date = _trailing_12_month_start(today)

    model: dict[str, Any] = {
        "pl": None,
        "ar": None,
        "ap": None,
        "modules": None,
        "errors": {},
    }

    try:
        model["pl"] = fetch_profit_loss_summary(client, from_date, today)
    except ServerOfflineError:
        raise
    except (ModuleUnavailableError, APIError) as exc:
        model["errors"]["pl"] = str(exc)

    try:
        model["ar"] = fetch_aged_receivables_total(client, today)
    except ServerOfflineError:
        raise
    except (ModuleUnavailableError, APIError) as exc:
        model["errors"]["ar"] = str(exc)

    try:
        model["ap"] = fetch_aged_payables_total(client, today)
    except ServerOfflineError:
        raise
    except (ModuleUnavailableError, APIError) as exc:
        model["errors"]["ap"] = str(exc)

    try:
        model["modules"] = fetch_module_health(client)
    except ServerOfflineError:
        raise
    except (ModuleUnavailableError, APIError) as exc:
        model["errors"]["modules"] = str(exc)

    return model
