"""Tests for ReconciliationView — offscreen Qt, mocked service layer."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


_UNMATCHED = [
    {"id": "bsl-1", "account_id": "acct-1", "txn_date": "2026-06-01",
     "description": "Coffee", "amount": "-9.90", "reference": "", "status": "UNMATCHED"},
    {"id": "bsl-2", "account_id": "acct-1", "txn_date": "2026-06-03",
     "description": "Sale", "amount": "55.00", "reference": "INV-1", "status": "UNMATCHED"},
]

_SUGGESTIONS = [
    {"id": "je-1", "ref": "JE-000031", "entry_date": "2026-06-01",
     "description": "Expense EX-1 (Coffee)", "status": "POSTED", "confidence": "HIGH"},
]


def _make_view(qapp, unmatched=None):
    from saebooks_desktop.views.reconciliation import ReconciliationView

    with patch(
        "saebooks_desktop.views.reconciliation.list_unmatched",
        return_value=unmatched if unmatched is not None else list(_UNMATCHED),
    ):
        view = ReconciliationView()
        view.load_account("acct-1", "Electronic Clearing")
        return view


def test_load_account_lists_unmatched_and_totals(qapp) -> None:
    view = _make_view(qapp)
    assert view._lines_model.rowCount() == 2
    # Running totals reflect the two unmatched lines (-9.90 + 55.00 = 45.10).
    assert "Unmatched: 2" in view._totals_label.text()
    assert "45.10" in view._totals_label.text()


def test_select_line_shows_suggestions(qapp) -> None:
    view = _make_view(qapp)
    view._lines_table.selectRow(0)
    with patch(
        "saebooks_desktop.views.reconciliation.suggest_matches",
        return_value=list(_SUGGESTIONS),
    ):
        view._on_line_clicked(None)
    # A "Match" button rendered for the single HIGH suggestion.
    from PySide6.QtWidgets import QPushButton

    buttons = view._detail_panel.findChildren(QPushButton)
    assert any(b.text() == "Match" for b in buttons)


def test_match_moves_line_and_updates_totals(qapp) -> None:
    view = _make_view(qapp)
    with patch(
        "saebooks_desktop.views.reconciliation.match",
        return_value={"id": "bsl-1", "status": "MATCHED"},
    ):
        view._on_match("bsl-1", "je-1")
    # bsl-1 left the unmatched set; matched-this-session has it.
    assert "Unmatched: 1" in view._totals_label.text()
    assert "Matched this session: 1" in view._totals_label.text()
    assert "matched" in view._banner.text().lower()


def test_unmatch_returns_line_to_unmatched(qapp) -> None:
    view = _make_view(qapp)
    with patch(
        "saebooks_desktop.views.reconciliation.match",
        return_value={"id": "bsl-1", "status": "MATCHED"},
    ):
        view._on_match("bsl-1", "je-1")
    with patch(
        "saebooks_desktop.views.reconciliation.unmatch",
        return_value={"id": "bsl-1", "status": "UNMATCHED"},
    ):
        view._on_unmatch("bsl-1")
    assert "Unmatched: 2" in view._totals_label.text()
    assert "Matched this session: 0" in view._totals_label.text()


def test_auto_match_calls_service_and_refreshes(qapp) -> None:
    view = _make_view(qapp)
    with patch(
        "saebooks_desktop.views.reconciliation.auto_match",
        return_value={"matched": 1, "skipped_ambiguous": 0, "skipped_no_candidate": 1},
    ) as am, patch(
        "saebooks_desktop.views.reconciliation.list_unmatched",
        return_value=[_UNMATCHED[1]],
    ):
        view._on_auto_match()
    am.assert_called_once()
    assert "1 line(s) matched" in view._banner.text()
    assert view._lines_model.rowCount() == 1


def test_match_offline_degrades_without_crash(qapp) -> None:
    from saebooks_desktop.services.api_client import ServerOfflineError

    view = _make_view(qapp)
    with patch(
        "saebooks_desktop.views.reconciliation.match",
        side_effect=ServerOfflineError("down"),
    ):
        view._on_match("bsl-1", "je-1")
    # Nothing changed; line stays unmatched, banner warns.
    assert "Unmatched: 2" in view._totals_label.text()
    assert "offline" in view._banner.text().lower()


def test_back_signal(qapp) -> None:
    view = _make_view(qapp)
    fired: list[bool] = []
    view.back_requested.connect(lambda: fired.append(True))
    view._back_btn.click()
    assert fired == [True]
