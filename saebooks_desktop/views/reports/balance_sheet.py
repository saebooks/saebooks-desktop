"""Balance Sheet report widget.

Displays assets, liabilities, and equity as at a chosen date.  Fetches from
``GET /api/v1/reports/balance_sheet``.

Columns: Account | Balance (right-aligned)
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem

from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.reports import get_balance_sheet
from saebooks_desktop.views.reports.base import DATE_MODE_AS_AT, BaseReportWidget

_COLUMNS = ["Account", "Balance"]
_COL_ACCOUNT = 0
_COL_BALANCE = 1


class BalanceSheetReport(BaseReportWidget):
    """Balance Sheet — assets, liabilities, equity at a point in time."""

    _REPORT_NAME = "balance_sheet"
    _COLUMNS = _COLUMNS

    def __init__(self, parent: object = None) -> None:
        super().__init__(date_mode=DATE_MODE_AS_AT, parent=parent)  # type: ignore[arg-type]
        self._client = APIClient()

        # Right-align Balance column header
        self._model.horizontalHeaderItem(_COL_BALANCE).setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

    # ---------------------------------------------------------------------- #

    def _run_report(self) -> None:
        self._model.removeRows(0, self._model.rowCount())
        self._set_status("loading", "Loading\u2026")
        self._offline_label.setVisible(False)

        try:
            data = get_balance_sheet(self._client, self._as_at_date())
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._set_status("error", "Could not load report — server offline.")
            self._offline_label.setVisible(True)
            return

        self._set_status()

        # Section headers + line items
        assets = data.get("assets", {})
        liabilities = data.get("liabilities", {})
        equity = data.get("equity", {})

        asset_lines = assets.get("ASSET", [])
        liability_lines = liabilities.get("LIABILITY", [])
        equity_lines = equity.get("EQUITY", [])

        has_data = bool(asset_lines or liability_lines or equity_lines)
        if not has_data:
            self._set_status("empty", "No data for the selected date.")
            return

        self._add_section("ASSETS", asset_lines)
        self._add_total_row("Total Assets", assets.get("total_assets", 0.0))

        self._add_section("LIABILITIES", liability_lines)
        self._add_total_row("Total Liabilities", liabilities.get("total_liabilities", 0.0))

        self._add_section("EQUITY", equity_lines)
        self._add_total_row("Total Equity", equity.get("total_equity", 0.0))

    def _add_section(self, heading: str, lines: list[dict[str, Any]]) -> None:
        """Insert a section header row followed by account line rows."""
        row = self._model.rowCount()
        self._model.insertRow(row)
        header_item = QStandardItem(heading)
        header_item.setData(True, Qt.ItemDataRole.UserRole + 1)  # mark as section header
        self._model.setItem(row, _COL_ACCOUNT, header_item)
        self._model.setItem(row, _COL_BALANCE, QStandardItem(""))

        for line in lines:
            r = self._model.rowCount()
            self._model.insertRow(r)
            name = line.get("account_name") or line.get("name") or ""
            balance = line.get("balance", 0.0)
            self._model.setItem(r, _COL_ACCOUNT, QStandardItem(f"  {name}"))
            bal_item = QStandardItem(f"{balance:,.2f}")
            bal_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._model.setItem(r, _COL_BALANCE, bal_item)

    def _add_total_row(self, label: str, amount: float) -> None:
        row = self._model.rowCount()
        self._model.insertRow(row)
        self._model.setItem(row, _COL_ACCOUNT, QStandardItem(label))
        total_item = QStandardItem(f"{amount:,.2f}")
        total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._model.setItem(row, _COL_BALANCE, total_item)
