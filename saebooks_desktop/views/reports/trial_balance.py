"""Trial Balance report widget.

Displays all accounts with Dr + Cr totals as at a chosen date.
Includes a footer row showing Sigma Dr = Sigma Cr.

Fetches from ``GET /api/v1/reports/trial_balance``.

Columns: Code | Name | Debit | Credit
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem

from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.reports import get_trial_balance
from saebooks_desktop.views.reports.base import DATE_MODE_AS_AT, BaseReportWidget

_COLUMNS = ["Code", "Name", "Debit", "Credit"]
_COL_CODE = 0
_COL_NAME = 1
_COL_DEBIT = 2
_COL_CREDIT = 3


class TrialBalanceReport(BaseReportWidget):
    """Trial Balance — all accounts with cumulative Dr + Cr totals."""

    _REPORT_NAME = "trial_balance"
    _COLUMNS = _COLUMNS

    def __init__(self, parent: object = None) -> None:
        super().__init__(date_mode=DATE_MODE_AS_AT, parent=parent)  # type: ignore[arg-type]
        self._client = APIClient()

        # Right-align numeric column headers
        for col in (_COL_DEBIT, _COL_CREDIT):
            self._model.horizontalHeaderItem(col).setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

    # ---------------------------------------------------------------------- #

    def _run_report(self) -> None:
        self._model.removeRows(0, self._model.rowCount())
        self._set_status("loading", "Loading\u2026")
        self._offline_label.setVisible(False)

        try:
            data = get_trial_balance(self._client, self._as_at_date())
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._set_status("error", "Could not load report — server offline.")
            self._offline_label.setVisible(True)
            return

        self._set_status()

        accounts = data.get("accounts", [])
        for line in accounts:
            row = self._model.rowCount()
            self._model.insertRow(row)
            self._model.setItem(row, _COL_CODE, QStandardItem(line.get("code") or ""))
            self._model.setItem(row, _COL_NAME, QStandardItem(line.get("name") or ""))

            debit_item = QStandardItem(f"{line.get('debit_total', 0.0):,.2f}")
            debit_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._model.setItem(row, _COL_DEBIT, debit_item)

            credit_item = QStandardItem(f"{line.get('credit_total', 0.0):,.2f}")
            credit_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._model.setItem(row, _COL_CREDIT, credit_item)

        # Footer row: totals
        total_debits = data.get("total_debits", 0.0)
        total_credits = data.get("total_credits", 0.0)
        self._append_totals_row(total_debits, total_credits)

        if not accounts:
            self._set_status("empty", "No data for the selected date.")

    def _append_totals_row(self, total_debits: float, total_credits: float) -> None:
        """Append the Sigma Dr / Sigma Cr footer row."""
        row = self._model.rowCount()
        self._model.insertRow(row)
        self._model.setItem(row, _COL_CODE, QStandardItem(""))
        totals_label = QStandardItem("TOTALS")
        self._model.setItem(row, _COL_NAME, totals_label)

        dr_item = QStandardItem(f"{total_debits:,.2f}")
        dr_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        # Store a flag so tests can identify this row
        dr_item.setData(True, Qt.ItemDataRole.UserRole + 10)
        self._model.setItem(row, _COL_DEBIT, dr_item)

        cr_item = QStandardItem(f"{total_credits:,.2f}")
        cr_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        cr_item.setData(True, Qt.ItemDataRole.UserRole + 10)
        self._model.setItem(row, _COL_CREDIT, cr_item)
