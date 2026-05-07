"""Tests for TrialBalanceReport widget — offscreen Qt, mocked API.

Key assertion: Sigma Dr == Sigma Cr (balanced trial balance).
"""
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


_SAMPLE_TB = {
    "as_of_date": "2024-06-30",
    "accounts": [
        {
            "account_id": "a1",
            "code": "1000",
            "name": "Cash at Bank",
            "account_type": "ASSET",
            "debit_total": 100000.0,
            "credit_total": 40000.0,
            "balance": 60000.0,
        },
        {
            "account_id": "a2",
            "code": "2000",
            "name": "Accounts Payable",
            "account_type": "LIABILITY",
            "debit_total": 5000.0,
            "credit_total": 25000.0,
            "balance": -20000.0,
        },
        {
            "account_id": "a3",
            "code": "4000",
            "name": "Revenue",
            "account_type": "INCOME",
            "debit_total": 0.0,
            "credit_total": 40000.0,
            "balance": -40000.0,
        },
    ],
    "total_debits": 105000.0,
    "total_credits": 105000.0,
    "balanced": True,
}


def _run_widget(qapp, data):
    from saebooks_desktop.views.reports.trial_balance import TrialBalanceReport

    w = TrialBalanceReport()
    with patch(
        "saebooks_desktop.views.reports.trial_balance.get_trial_balance",
        return_value=data,
    ):
        w._run_report()
    return w


class TestTrialBalanceReportInstantiation:
    def test_instantiates(self, qapp) -> None:
        from saebooks_desktop.views.reports.trial_balance import TrialBalanceReport

        w = TrialBalanceReport()
        assert w is not None

    def test_has_four_columns(self, qapp) -> None:
        from saebooks_desktop.views.reports.trial_balance import TrialBalanceReport

        w = TrialBalanceReport()
        assert w._model.columnCount() == 4

    def test_column_headers(self, qapp) -> None:
        from saebooks_desktop.views.reports.trial_balance import TrialBalanceReport

        w = TrialBalanceReport()
        expected = ["Code", "Name", "Debit", "Credit"]
        actual = [w._model.horizontalHeaderItem(i).text() for i in range(4)]
        assert actual == expected

    def test_report_name(self, qapp) -> None:
        from saebooks_desktop.views.reports.trial_balance import TrialBalanceReport

        w = TrialBalanceReport()
        assert w._REPORT_NAME == "trial_balance"


class TestTrialBalanceReportPopulation:
    def test_account_rows_plus_totals_row(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_TB)
        # 3 account rows + 1 totals row
        assert w._model.rowCount() == 4

    def test_first_row_code(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_TB)
        assert w._model.item(0, 0).text() == "1000"

    def test_first_row_name(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_TB)
        assert w._model.item(0, 1).text() == "Cash at Bank"

    def test_debit_column_formatted(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_TB)
        assert "100,000.00" in w._model.item(0, 2).text()

    def test_credit_column_formatted(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_TB)
        assert "40,000.00" in w._model.item(0, 3).text()

    def test_totals_row_is_last(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_TB)
        last = w._model.rowCount() - 1
        assert w._model.item(last, 1).text() == "TOTALS"

    def test_totals_sigma_dr_equals_sigma_cr(self, qapp) -> None:
        """Totals row Debit and Credit must match total_debits / total_credits."""
        w = _run_widget(qapp, _SAMPLE_TB)
        last = w._model.rowCount() - 1
        dr_text = w._model.item(last, 2).text().replace(",", "")
        cr_text = w._model.item(last, 3).text().replace(",", "")
        assert float(dr_text) == pytest.approx(105000.0)
        assert float(cr_text) == pytest.approx(105000.0)

    def test_offline_on_error(self, qapp) -> None:
        from saebooks_desktop.services.api_client import ServerOfflineError
        from saebooks_desktop.views.reports.trial_balance import TrialBalanceReport

        w = TrialBalanceReport()
        with patch(
            "saebooks_desktop.views.reports.trial_balance.get_trial_balance",
            side_effect=ServerOfflineError("down"),
        ):
            w._run_report()
        assert not w._offline_label.isHidden()

    def test_empty_state_on_no_accounts(self, qapp) -> None:
        empty = {**_SAMPLE_TB, "accounts": [], "total_debits": 0.0, "total_credits": 0.0}
        w = _run_widget(qapp, empty)
        assert not w._status_label.isHidden()

    def test_amounts_right_aligned(self, qapp) -> None:
        from PySide6.QtCore import Qt

        w = _run_widget(qapp, _SAMPLE_TB)
        debit_item = w._model.item(0, 2)
        assert debit_item.textAlignment() & Qt.AlignmentFlag.AlignRight

    def test_export_signal(self, qapp, tmp_path) -> None:
        from saebooks_desktop.views.reports.trial_balance import TrialBalanceReport

        w = TrialBalanceReport()
        received: list[str] = []
        w.export_requested.connect(received.append)
        w._choose_export_path = lambda: str(tmp_path / "trial_balance.csv")
        w._export_btn.click()
        assert received == ["trial_balance"]
