"""Profit & Loss report widget.

Displays income and expenses for a date range.  Fetches from
``GET /api/v1/reports/profit_loss``.

Columns: Account | Amount (right-aligned)
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem

from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.reports import get_profit_loss
from saebooks_desktop.views.reports.base import DATE_MODE_RANGE, BaseReportWidget

_COLUMNS = ["Account", "Amount"]
_COL_ACCOUNT = 0
_COL_AMOUNT = 1


class ProfitLossReport(BaseReportWidget):
    """Profit & Loss — income and expenses for a date range."""

    _REPORT_NAME = "profit_loss"
    _COLUMNS = _COLUMNS

    def __init__(self, parent: object = None) -> None:
        super().__init__(date_mode=DATE_MODE_RANGE, parent=parent)  # type: ignore[arg-type]
        self._client = APIClient()

        # Right-align Amount column header
        self._model.horizontalHeaderItem(_COL_AMOUNT).setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

    # ---------------------------------------------------------------------- #

    def _run_report(self) -> None:
        self._model.removeRows(0, self._model.rowCount())
        self._set_status("loading", "Loading\u2026")
        self._offline_label.setVisible(False)

        try:
            data = get_profit_loss(self._client, self._from_date(), self._to_date())
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._set_status("error", "Could not load report — server offline.")
            self._offline_label.setVisible(True)
            return

        self._set_status()

        income = data.get("income", {})
        expenses = data.get("expenses", {})

        income_lines = (
            income.get("INCOME", [])
            + income.get("OTHER_INCOME", [])
        )
        expense_lines = (
            expenses.get("EXPENSE", [])
            + expenses.get("COST_OF_SALES", [])
            + expenses.get("OTHER_EXPENSE", [])
        )

        if not income_lines and not expense_lines:
            self._set_status("empty", "No data for the selected period.")
            return

        # Income section
        self._add_section("INCOME", income.get("INCOME", []))
        self._add_section("OTHER INCOME", income.get("OTHER_INCOME", []))
        self._add_total_row("Total Income", income.get("total_income", 0.0))

        # Expense section
        self._add_section("COST OF SALES", expenses.get("COST_OF_SALES", []))
        self._add_section("EXPENSES", expenses.get("EXPENSE", []))
        self._add_section("OTHER EXPENSES", expenses.get("OTHER_EXPENSE", []))
        self._add_total_row("Total Expenses", expenses.get("total_expenses", 0.0))

        # Net profit
        self._add_total_row("Net Profit", data.get("net_profit", 0.0))

    def _add_section(self, heading: str, lines: list[dict[str, Any]]) -> None:
        if not lines:
            return
        row = self._model.rowCount()
        self._model.insertRow(row)
        self._model.setItem(row, _COL_ACCOUNT, QStandardItem(heading))
        self._model.setItem(row, _COL_AMOUNT, QStandardItem(""))

        for line in lines:
            r = self._model.rowCount()
            self._model.insertRow(r)
            name = line.get("account_name") or line.get("name") or ""
            amount = line.get("amount", 0.0)
            self._model.setItem(r, _COL_ACCOUNT, QStandardItem(f"  {name}"))
            amt_item = QStandardItem(f"{amount:,.2f}")
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._model.setItem(r, _COL_AMOUNT, amt_item)

    def _add_total_row(self, label: str, amount: float) -> None:
        row = self._model.rowCount()
        self._model.insertRow(row)
        self._model.setItem(row, _COL_ACCOUNT, QStandardItem(label))
        total_item = QStandardItem(f"{amount:,.2f}")
        total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._model.setItem(row, _COL_AMOUNT, total_item)
