"""Reports service wrappers — thin helpers over APIClient.get().

Each function fetches a structured report from the respective
``GET /api/v1/reports/<slug>`` endpoint.

If an endpoint is not yet deployed on the API server, the function
will raise ``ServerOfflineError`` or ``APIError``; callers should
handle those gracefully (offline banner, empty state).
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def get_balance_sheet(client: APIClient, as_at_date: str) -> dict[str, Any]:
    """Fetch the balance sheet as at *as_at_date* (ISO-8601 string).

    Returns the full response dict from ``GET /api/v1/reports/balance_sheet``.
    Expected shape::

        {
            "as_of_date": "2024-06-30",
            "assets":      {"ASSET": [...], "total_assets": float},
            "liabilities": {"LIABILITY": [...], "total_liabilities": float},
            "equity":      {"EQUITY": [...], "total_equity": float},
            "balanced":    bool,
            "difference":  float,
        }

    Each line item in the section lists has: account_id, account_name,
    code, balance (float).

    # TODO: endpoint /api/v1/reports/balance_sheet must exist on the server.
    """
    return client.get("/api/v1/reports/balance_sheet", params={"as_of_date": as_at_date})


def get_profit_loss(
    client: APIClient, date_from: str, date_to: str
) -> dict[str, Any]:
    """Fetch the P&L for the period [*date_from*, *date_to*] (ISO-8601 strings).

    Returns the full response dict from ``GET /api/v1/reports/profit_loss``.
    Expected shape::

        {
            "from_date": "2024-07-01",
            "to_date":   "2024-06-30",
            "income": {
                "INCOME":       [...],
                "OTHER_INCOME": [...],
                "total_income": float,
            },
            "expenses": {
                "EXPENSE":        [...],
                "COST_OF_SALES":  [...],
                "OTHER_EXPENSE":  [...],
                "total_expenses": float,
            },
            "net_profit": float,
        }

    Each line item has: account_id, account_name, code, amount (float).

    # TODO: endpoint /api/v1/reports/profit_loss must exist on the server.
    """
    return client.get(
        "/api/v1/reports/profit_loss",
        params={"from_date": date_from, "to_date": date_to},
    )


def get_trial_balance(client: APIClient, as_at_date: str) -> dict[str, Any]:
    """Fetch the trial balance as at *as_at_date* (ISO-8601 string).

    Returns the full response dict from ``GET /api/v1/reports/trial_balance``.
    Expected shape::

        {
            "as_of_date":     "2024-06-30",
            "accounts": [
                {
                    "account_id": "...",
                    "code":        "1000",
                    "name":        "Cash at Bank",
                    "account_type": "ASSET",
                    "debit_total":  float,
                    "credit_total": float,
                    "balance":      float,
                },
                ...
            ],
            "total_debits":  float,
            "total_credits": float,
            "balanced":      bool,
        }

    # TODO: endpoint /api/v1/reports/trial_balance must exist on the server.
    """
    return client.get(
        "/api/v1/reports/trial_balance", params={"as_of_date": as_at_date}
    )


def get_aged_receivables(client: APIClient, as_at_date: str) -> dict[str, Any]:
    """Fetch the aged receivables report as at *as_at_date* (ISO-8601 string).

    Returns the full response dict from
    ``GET /api/v1/reports/aged_receivables``.  Expected shape::

        {
            "as_of_date": "2024-06-30",
            "buckets": ["current", "1-30 days", "31-60 days", "61-90 days", "90+ days"],
            "contacts": [
                {
                    "contact_id":   "...",
                    "contact_name": "Acme Corp",
                    "current":      float,
                    "1-30 days":    float,
                    "31-60 days":   float,
                    "61-90 days":   float,
                    "90+ days":     float,
                    "total":        float,
                },
                ...
            ],
            "totals": {"current": float, ..., "total": float},
        }

    # TODO: endpoint /api/v1/reports/aged_receivables must exist on the server.
    """
    return client.get(
        "/api/v1/reports/aged_receivables", params={"as_of_date": as_at_date}
    )


def get_aged_payables(client: APIClient, as_at_date: str) -> dict[str, Any]:
    """Fetch the aged payables report as at *as_at_date* (ISO-8601 string).

    Returns the full response dict from
    ``GET /api/v1/reports/aged_payables``.  Response shape is identical to
    ``get_aged_receivables`` but covers bills/payables.

    # TODO: endpoint /api/v1/reports/aged_payables must exist on the server.
    """
    return client.get(
        "/api/v1/reports/aged_payables", params={"as_of_date": as_at_date}
    )
