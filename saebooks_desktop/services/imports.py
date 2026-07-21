"""Bank statement import service — thin helpers over the engine wizard API.

Wraps ``/api/v1/imports/wizards`` for the bank-statement (CSV/OFX) flow:
start a wizard for a chart account, push the raw file text, commit. The
engine auto-detects the CSV format (CBA / ANZ / NAB / Westpac / generic
header) and the OFX variant — there is no manual column-mapping step, so
the desktop flow is: pick account → choose file → import.

``run_bank_import`` is the one-call convenience the view uses; the
granular ``start`` / ``upload`` / ``commit`` helpers are exposed for tests
and for any future stepped/preview UI.
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services.api_client import APIClient


def start_bank_import(client: APIClient, account_id: str) -> str:
    """Start a ``bank_csv`` wizard for a chart account; return the wizard id.

    ``POST /api/v1/imports/wizards`` body
    ``{"kind": "bank_csv", "initial": {"account_id": account_id}}`` → 201
    ``{"wizard_id", "step", "state"}``. ``bank_csv`` also accepts OFX — the
    engine sniffs the content and parses OFX when it sees an OFX header.
    """
    resp = client.post(
        "/api/v1/imports/wizards",
        json={"kind": "bank_csv", "initial": {"account_id": account_id}},
    )
    return resp["wizard_id"]


def upload_bank_file(
    client: APIClient, wizard_id: str, raw: str, account_id: str
) -> dict[str, Any]:
    """Push the raw statement text into the wizard state.

    ``POST /api/v1/imports/wizards/{id}/step`` with the raw file content and
    the ``_completed`` sentinel so the wizard is ready to commit.
    """
    return client.post(
        f"/api/v1/imports/wizards/{wizard_id}/step",
        json={
            "step": 0,
            "patch": {"raw": raw, "account_id": account_id, "_completed": True},
        },
    )


def commit_import(client: APIClient, wizard_id: str) -> dict[str, Any]:
    """Commit the wizard — parse + persist the lines.

    ``POST /api/v1/imports/wizards/{id}/commit`` → ``{inserted, total}``
    for a bank import (``inserted`` counts new rows; duplicates — matched on
    a deterministic external id — are skipped, so ``inserted`` may be less
    than ``total``).
    """
    return client.post(f"/api/v1/imports/wizards/{wizard_id}/commit")


def run_bank_import(
    client: APIClient, account_id: str, raw: str
) -> dict[str, Any]:
    """Start → upload → commit in one call. Returns ``{inserted, total}``."""
    wizard_id = start_bank_import(client, account_id)
    upload_bank_file(client, wizard_id, raw, account_id)
    return commit_import(client, wizard_id)
