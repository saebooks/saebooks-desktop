"""Cashbook Reports view — the summary report shown as "Reports" in cashbook mode.

Per the adjudicated navigation verdict, cashbook-mode navigation is
Cashbook / Reports / Settings plus the single "Full accounting →"
doorway. This view backs the Reports item: a date-ranged rendering of
``GET /api/v1/cashbook/summary`` — totals (money in / money out / net,
tax collected / tax paid using the brand's ``tax_label``) and the
by-category breakdown table.

Degraded states mirror the sibling views (per-panel degrade intact):
  - ``ServerOfflineError`` → offline banner (objectName ``offline_banner``).
  - ``ModuleUnavailableError`` → module banner (objectName ``module_banner``)
    carrying the engine's error message.
"""
from __future__ import annotations

import datetime
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.branding import get_brand
from saebooks_desktop.services.api_client import (
    APIClient,
    APIError,
    ModuleUnavailableError,
    ServerOfflineError,
)
from saebooks_desktop.services.cashbook import get_summary
from saebooks_desktop.views.cashbook import _extract_summary

_COL_CATEGORY = 0
_COL_DIRECTION = 1
_COL_COUNT = 2
_COL_AMOUNT = 3

_COLUMNS = ["Category", "Direction", "Entries", "Amount"]

_DIRECTION_LABELS = {"income": "In", "expense": "Out"}


class CashbookReportView(QWidget):
    """Date-ranged cashbook summary — totals strip + by-category table."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._client = APIClient()
        self._tax_label_word = get_brand().tax_label

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # --- Offline / module banners ---
        self._offline_banner = QLabel("Server offline — showing cached data")
        self._offline_banner.setObjectName("offline_banner")
        self._offline_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._offline_banner.setStyleSheet(
            "background: #fff3cd; color: #856404; padding: 4px;"
        )
        self._offline_banner.setVisible(False)
        layout.addWidget(self._offline_banner)

        self._module_banner = QLabel("")
        self._module_banner.setObjectName("module_banner")
        self._module_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._module_banner.setStyleSheet(
            "background: #f8d7da; color: #721c24; padding: 4px;"
        )
        self._module_banner.setVisible(False)
        layout.addWidget(self._module_banner)

        # --- Date range + refresh row ---
        range_widget = QWidget()
        range_layout = QHBoxLayout(range_widget)
        range_layout.setContentsMargins(8, 4, 8, 4)

        today = datetime.date.today()
        range_layout.addWidget(QLabel("From:"))
        self._from_edit = QDateEdit()
        self._from_edit.setCalendarPopup(True)
        self._from_edit.setDate(QDate(today.year, 1, 1))
        range_layout.addWidget(self._from_edit)

        range_layout.addWidget(QLabel("To:"))
        self._to_edit = QDateEdit()
        self._to_edit.setCalendarPopup(True)
        self._to_edit.setDate(QDate.currentDate())
        range_layout.addWidget(self._to_edit)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self.reload)
        range_layout.addWidget(self._refresh_btn)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        range_layout.addWidget(spacer)

        layout.addWidget(range_widget)

        # --- Totals strip ---
        totals_widget = QWidget()
        totals_layout = QHBoxLayout(totals_widget)
        totals_layout.setContentsMargins(8, 4, 8, 4)

        self._money_in_label = QLabel("Money in: —")
        self._money_out_label = QLabel("Money out: —")
        self._net_label = QLabel("Net: —")
        self._gst_collected_label = QLabel(f"{self._tax_label_word} collected: —")
        self._gst_paid_label = QLabel(f"{self._tax_label_word} paid: —")
        for label in (
            self._money_in_label,
            self._money_out_label,
            self._net_label,
            self._gst_collected_label,
            self._gst_paid_label,
        ):
            totals_layout.addWidget(label)
        totals_layout.addStretch()

        layout.addWidget(totals_widget)

        # --- By-category table ---
        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

    def showEvent(self, event) -> None:  # type: ignore[override]
        """First display triggers the initial load (construction stays
        network-free for tests and window startup)."""
        super().showEvent(event)
        if not getattr(self, "_loaded_once", False):
            self._loaded_once = True
            self.load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, client: APIClient | None = None) -> None:
        """(Re)fetch the summary for the selected range; degrade gracefully."""
        if client is not None:
            self._client = client

        self._offline_banner.setVisible(False)
        self._module_banner.setVisible(False)

        date_from = self._from_edit.date().toString("yyyy-MM-dd")
        date_to = self._to_edit.date().toString("yyyy-MM-dd")

        try:
            summary = get_summary(self._client, date_from, date_to)
        except ServerOfflineError:
            self._offline_banner.setVisible(True)
            return
        except ModuleUnavailableError as exc:
            self._module_banner.setText(str(exc))
            self._module_banner.setVisible(True)
            return
        except (APIError, Exception):  # noqa: BLE001 — never raise out of load()
            return

        self._populate_totals(summary)
        self._populate_categories(summary.get("by_category") or [])

    def reload(self) -> None:
        """Alias for ``load()`` with the current client — matches sibling views."""
        self.load()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _populate_totals(self, summary: dict[str, Any]) -> None:
        values = _extract_summary(summary)
        self._money_in_label.setText(f"Money in: {values['income']}")
        self._money_out_label.setText(f"Money out: {values['expense']}")
        self._net_label.setText(f"Net: {values['net']}")
        self._gst_collected_label.setText(
            f"{self._tax_label_word} collected: {values['gst_collected']}"
        )
        self._gst_paid_label.setText(
            f"{self._tax_label_word} paid: {values['gst_paid']}"
        )

    def _populate_categories(self, rows: list[dict[str, Any]]) -> None:
        self._table.setRowCount(0)
        for cat in rows:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(
                row,
                _COL_CATEGORY,
                QTableWidgetItem(cat.get("label") or cat.get("code") or ""),
            )
            direction = cat.get("direction") or ""
            self._table.setItem(
                row,
                _COL_DIRECTION,
                QTableWidgetItem(_DIRECTION_LABELS.get(direction, direction)),
            )
            count_item = QTableWidgetItem(str(cat.get("count") or 0))
            count_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(row, _COL_COUNT, count_item)
            amount_item = QTableWidgetItem(str(cat.get("amount") or ""))
            amount_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(row, _COL_AMOUNT, amount_item)
