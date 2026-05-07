"""Tests for ProfitLossReport widget — offscreen Qt, mocked API."""
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


_SAMPLE_PL = {
    "from_date": "2024-07-01",
    "to_date": "2024-12-31",
    "income": {
        "INCOME": [
            {"account_id": "i1", "account_name": "Consulting Revenue", "code": "4000", "amount": 120000.0},
        ],
        "OTHER_INCOME": [],
        "total_income": 120000.0,
    },
    "expenses": {
        "EXPENSE": [
            {"account_id": "x1", "account_name": "Wages", "code": "6100", "amount": 80000.0},
        ],
        "COST_OF_SALES": [],
        "OTHER_EXPENSE": [],
        "total_expenses": 80000.0,
    },
    "net_profit": 40000.0,
}


def _run_widget(qapp, data):
    from saebooks_desktop.views.reports.profit_loss import ProfitLossReport

    w = ProfitLossReport()
    with patch(
        "saebooks_desktop.views.reports.profit_loss.get_profit_loss",
        return_value=data,
    ):
        w._run_report()
    return w


class TestProfitLossReportInstantiation:
    def test_instantiates(self, qapp) -> None:
        from saebooks_desktop.views.reports.profit_loss import ProfitLossReport

        w = ProfitLossReport()
        assert w is not None

    def test_has_two_columns(self, qapp) -> None:
        from saebooks_desktop.views.reports.profit_loss import ProfitLossReport

        w = ProfitLossReport()
        assert w._model.columnCount() == 2

    def test_column_headers(self, qapp) -> None:
        from saebooks_desktop.views.reports.profit_loss import ProfitLossReport

        w = ProfitLossReport()
        assert w._model.horizontalHeaderItem(0).text() == "Account"
        assert w._model.horizontalHeaderItem(1).text() == "Amount"

    def test_uses_date_range_mode(self, qapp) -> None:
        from saebooks_desktop.views.reports.base import DATE_MODE_RANGE
        from saebooks_desktop.views.reports.profit_loss import ProfitLossReport

        w = ProfitLossReport()
        assert w._date_mode == DATE_MODE_RANGE

    def test_report_name(self, qapp) -> None:
        from saebooks_desktop.views.reports.profit_loss import ProfitLossReport

        w = ProfitLossReport()
        assert w._REPORT_NAME == "profit_loss"


class TestProfitLossReportPopulation:
    def test_rows_populated(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_PL)
        assert w._model.rowCount() > 0

    def test_income_section_present(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_PL)
        texts = [w._model.item(r, 0).text() for r in range(w._model.rowCount())]
        assert "INCOME" in texts

    def test_total_income_row_present(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_PL)
        texts = [w._model.item(r, 0).text() for r in range(w._model.rowCount())]
        assert "Total Income" in texts

    def test_net_profit_row_present(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_PL)
        texts = [w._model.item(r, 0).text() for r in range(w._model.rowCount())]
        assert "Net Profit" in texts

    def test_net_profit_value_formatted(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_PL)
        for r in range(w._model.rowCount()):
            if w._model.item(r, 0).text() == "Net Profit":
                assert "40,000.00" in w._model.item(r, 1).text()
                return
        pytest.fail("Net Profit row not found")

    def test_offline_on_error(self, qapp) -> None:
        from saebooks_desktop.services.api_client import ServerOfflineError
        from saebooks_desktop.views.reports.profit_loss import ProfitLossReport

        w = ProfitLossReport()
        with patch(
            "saebooks_desktop.views.reports.profit_loss.get_profit_loss",
            side_effect=ServerOfflineError("down"),
        ):
            w._run_report()
        assert not w._offline_label.isHidden()

    def test_empty_state_on_empty_response(self, qapp) -> None:
        w = _run_widget(qapp, {})
        assert not w._status_label.isHidden()

    def test_empty_sections_not_shown(self, qapp) -> None:
        """Sections with no line items must not add a header row."""
        w = _run_widget(qapp, _SAMPLE_PL)
        texts = [w._model.item(r, 0).text() for r in range(w._model.rowCount())]
        # OTHER_INCOME and COST_OF_SALES have empty lists → no header row
        assert "OTHER INCOME" not in texts
        assert "COST OF SALES" not in texts

    def test_amount_right_aligned(self, qapp) -> None:
        from PySide6.QtCore import Qt

        w = _run_widget(qapp, _SAMPLE_PL)
        for r in range(w._model.rowCount()):
            item = w._model.item(r, 1)
            if item and item.text() and item.text() != "":
                assert item.textAlignment() & Qt.AlignmentFlag.AlignRight
                break

    def test_export_signal(self, qapp, tmp_path) -> None:
        from saebooks_desktop.views.reports.profit_loss import ProfitLossReport

        w = ProfitLossReport()
        received: list[str] = []
        w.export_requested.connect(received.append)
        w._choose_export_path = lambda: str(tmp_path / "profit_loss.csv")
        w._export_btn.click()
        assert received == ["profit_loss"]
