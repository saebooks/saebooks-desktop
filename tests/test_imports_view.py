"""Tests for ImportStatementView — offscreen Qt, mocked service layer.

No real HTTP: the service functions imported into the view module
(``list_reconcilable_accounts``, ``run_bank_import``) are patched.
"""
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


_ACCOUNTS = [
    {"id": "acct-1", "code": "1-1180", "name": "Undeposited Funds"},
    {"id": "acct-2", "code": "1-1190", "name": "Electronic Clearing"},
]


def _make_view(qapp, accounts=None, accounts_side_effect=None):
    from saebooks_desktop.views.imports import ImportStatementView

    kw = {}
    if accounts_side_effect is not None:
        kw["side_effect"] = accounts_side_effect
    else:
        kw["return_value"] = accounts if accounts is not None else _ACCOUNTS
    with patch("saebooks_desktop.views.imports.list_reconcilable_accounts", **kw):
        return ImportStatementView()


def test_instantiates_and_populates_accounts(qapp) -> None:
    view = _make_view(qapp)
    assert view._account_combo.count() == 2
    assert view._account_combo.itemData(0) == "acct-1"
    # Import disabled until a file is chosen.
    assert view._import_btn.isEnabled() is False


def test_load_file_enables_import_and_previews(qapp, tmp_path) -> None:
    view = _make_view(qapp)
    csv = tmp_path / "stmt.csv"
    csv.write_text("Date,Description,Amount\n2026-06-01,Coffee,-9.90\n")
    view._load_file(str(csv))
    assert "Coffee" in view._preview.toPlainText()
    assert view._import_btn.isEnabled() is True
    assert view._file_label.text() == "stmt.csv"


def test_import_success_emits_done_and_shows_result(qapp, tmp_path) -> None:
    view = _make_view(qapp)
    csv = tmp_path / "stmt.csv"
    csv.write_text("Date,Description,Amount\n2026-06-01,Coffee,-9.90\n")
    view._load_file(str(csv))

    fired: list[bool] = []
    view.import_done.connect(lambda: fired.append(True))
    with patch(
        "saebooks_desktop.views.imports.run_bank_import",
        return_value={"inserted": 1, "total": 1},
    ):
        view._on_import()
    assert fired == [True]
    assert not view._banner.isHidden()
    assert "Imported 1 of 1" in view._banner.text()


def test_import_reports_duplicates(qapp, tmp_path) -> None:
    view = _make_view(qapp)
    csv = tmp_path / "s.csv"
    csv.write_text("Date,Description,Amount\n2026-06-01,A,1.00\n2026-06-02,B,2.00\n")
    view._load_file(str(csv))
    with patch(
        "saebooks_desktop.views.imports.run_bank_import",
        return_value={"inserted": 1, "total": 2},
    ):
        view._on_import()
    assert "1 of 2" in view._banner.text()
    assert "duplicate" in view._banner.text()


def test_import_offline_degrades_without_crash(qapp, tmp_path) -> None:
    from saebooks_desktop.services.api_client import ServerOfflineError

    view = _make_view(qapp)
    csv = tmp_path / "s.csv"
    csv.write_text("Date,Description,Amount\n2026-06-01,A,1.00\n")
    view._load_file(str(csv))
    with patch(
        "saebooks_desktop.views.imports.run_bank_import",
        side_effect=ServerOfflineError("down"),
    ):
        view._on_import()
    assert not view._banner.isHidden()
    assert "offline" in view._banner.text().lower()
    # Import button re-enabled so the user can retry.
    assert view._import_btn.isEnabled() is True


def test_accounts_offline_degrades(qapp) -> None:
    from saebooks_desktop.services.api_client import ServerOfflineError

    view = _make_view(qapp, accounts_side_effect=ServerOfflineError("down"))
    assert view._account_combo.count() == 0
    assert not view._banner.isHidden()
