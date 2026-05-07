"""Tests for BalanceSheetReport widget — offscreen Qt, mocked API."""
from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


_SAMPLE_BS = {
    "as_of_date": "2024-06-30",
    "assets": {
        "ASSET": [
            {"account_id": "a1", "account_name": "Cash at Bank", "code": "1000", "balance": 50000.0},
            {"account_id": "a2", "account_name": "Accounts Receivable", "code": "1100", "balance": 12500.0},
        ],
        "total_assets": 62500.0,
    },
    "liabilities": {
        "LIABILITY": [
            {"account_id": "l1", "account_name": "Accounts Payable", "code": "2000", "balance": 8000.0},
        ],
        "total_liabilities": 8000.0,
    },
    "equity": {
        "EQUITY": [
            {"account_id": "e1", "account_name": "Retained Earnings", "code": "3000", "balance": 54500.0},
        ],
        "total_equity": 54500.0,
    },
    "balanced": True,
    "difference": 0.0,
}


def _make_widget(qapp, data=None, side_effect=None):
    from saebooks_desktop.views.reports.balance_sheet import BalanceSheetReport

    target = "saebooks_desktop.views.reports.balance_sheet.get_balance_sheet"
    if side_effect is not None:
        with patch(target, side_effect=side_effect):
            w = BalanceSheetReport()
    else:
        with patch(target, return_value=data if data is not None else {}):
            w = BalanceSheetReport()
    return w


class TestBalanceSheetReportInstantiation:
    def test_instantiates(self, qapp) -> None:
        w = _make_widget(qapp)
        assert w is not None

    def test_has_two_columns(self, qapp) -> None:
        w = _make_widget(qapp)
        assert w._model.columnCount() == 2

    def test_column_headers(self, qapp) -> None:
        w = _make_widget(qapp)
        assert w._model.horizontalHeaderItem(0).text() == "Account"
        assert w._model.horizontalHeaderItem(1).text() == "Balance"

    def test_report_name(self, qapp) -> None:
        w = _make_widget(qapp)
        assert w._REPORT_NAME == "balance_sheet"


class TestBalanceSheetReportRunReport:
    def _run(self, qapp, data):
        from saebooks_desktop.views.reports.balance_sheet import BalanceSheetReport

        w = BalanceSheetReport()
        with patch(
            "saebooks_desktop.views.reports.balance_sheet.get_balance_sheet",
            return_value=data,
        ):
            w._run_report()
        return w

    def test_rows_populated(self, qapp) -> None:
        w = self._run(qapp, _SAMPLE_BS)
        # Expect: ASSETS header + 2 lines + total, LIABILITIES header + 1 + total,
        # EQUITY header + 1 + total = 3+3+3 = 9 rows
        assert w._model.rowCount() > 0

    def test_assets_header_present(self, qapp) -> None:
        w = self._run(qapp, _SAMPLE_BS)
        texts = [w._model.item(r, 0).text() for r in range(w._model.rowCount())]
        assert "ASSETS" in texts

    def test_liabilities_header_present(self, qapp) -> None:
        w = self._run(qapp, _SAMPLE_BS)
        texts = [w._model.item(r, 0).text() for r in range(w._model.rowCount())]
        assert "LIABILITIES" in texts

    def test_equity_header_present(self, qapp) -> None:
        w = self._run(qapp, _SAMPLE_BS)
        texts = [w._model.item(r, 0).text() for r in range(w._model.rowCount())]
        assert "EQUITY" in texts

    def test_total_assets_row_present(self, qapp) -> None:
        w = self._run(qapp, _SAMPLE_BS)
        texts = [w._model.item(r, 0).text() for r in range(w._model.rowCount())]
        assert "Total Assets" in texts

    def test_balance_amount_formatted(self, qapp) -> None:
        w = self._run(qapp, _SAMPLE_BS)
        # Find Cash at Bank row
        for r in range(w._model.rowCount()):
            if "Cash at Bank" in (w._model.item(r, 0).text() or ""):
                bal = w._model.item(r, 1).text()
                assert "50,000.00" in bal
                return
        pytest.fail("Cash at Bank row not found")

    def test_offline_on_error(self, qapp) -> None:
        from saebooks_desktop.services.api_client import ServerOfflineError
        from saebooks_desktop.views.reports.balance_sheet import BalanceSheetReport

        w = BalanceSheetReport()
        with patch(
            "saebooks_desktop.views.reports.balance_sheet.get_balance_sheet",
            side_effect=ServerOfflineError("down"),
        ):
            w._run_report()
        assert not w._offline_label.isHidden()

    def test_empty_state_on_empty_response(self, qapp) -> None:
        w = self._run(qapp, {})
        assert not w._status_label.isHidden()

    def test_export_signal_emitted(self, qapp, tmp_path) -> None:
        w = _make_widget(qapp)
        received: list[str] = []
        w.export_requested.connect(received.append)
        w._choose_export_path = lambda: str(tmp_path / "balance_sheet.csv")
        w._export_btn.click()
        assert received == ["balance_sheet"]

    def test_balance_right_aligned(self, qapp) -> None:
        from PySide6.QtCore import Qt

        w = self._run(qapp, _SAMPLE_BS)
        for r in range(w._model.rowCount()):
            item = w._model.item(r, 1)
            if item and item.text() and item.text() != "":
                alignment = item.textAlignment()
                assert alignment & Qt.AlignmentFlag.AlignRight
                break
