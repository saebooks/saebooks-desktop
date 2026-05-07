"""Recurring Invoices list view.

Displays a paginated QTableView of recurring invoices fetched from
``GET /api/v1/recurring_invoices``.

Columns: Name | Contact | Frequency | Next Date | Status

Filter toolbar (above table):
  - Status QComboBox  (All / Active / Paused / Ended)
  - "New Recurring Invoice" QPushButton

Action button per row (via toolbar):
  - "Run Now" QPushButton — calls ``POST /api/v1/recurring_invoices/{id}/run``
    for the currently selected row.

Signals:
  - ``recurring_invoice_selected(str)`` — emitted on double-click with the id.
  - ``new_recurring_invoice_requested()`` — emitted when "New" is clicked.

Pagination: "Load more" button appends the next page.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.api_client import APIClient, APIError, ServerOfflineError
from saebooks_desktop.services.recurring_invoices import (
    list_recurring_invoices,
    run_recurring_invoice,
)

# Column indices
_COL_NAME = 0
_COL_CONTACT = 1
_COL_FREQUENCY = 2
_COL_NEXT_DATE = 3
_COL_STATUS = 4

_COLUMNS = ["Name", "Contact", "Frequency", "Next Date", "Status"]

_STATUS_OPTIONS = ["All", "Active", "Paused", "Ended"]

_PAGE_SIZE = 50


class RecurringInvoicesView(QWidget):
    """Recurring invoices list view.

    Fetches from ``/api/v1/recurring_invoices`` via REST and renders a
    filterable, paginated table.  Emits ``recurring_invoice_selected(id)``
    on double-click.  "Run Now" button generates the next invoice for the
    selected row immediately.
    """

    recurring_invoice_selected = Signal(str)
    new_recurring_invoice_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._client = APIClient()
        self._current_page = 1
        self._has_more = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # --- Filter toolbar ---
        toolbar_widget = QWidget()
        toolbar_layout = QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)

        toolbar_layout.addWidget(QLabel("Status:"))
        self._status_combo = QComboBox()
        self._status_combo.addItems(_STATUS_OPTIONS)
        self._status_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self._status_combo)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        toolbar_layout.addWidget(spacer)

        self._run_now_btn = QPushButton("Run Now")
        self._run_now_btn.setEnabled(False)
        self._run_now_btn.clicked.connect(self._on_run_now_clicked)
        toolbar_layout.addWidget(self._run_now_btn)

        self._new_btn = QPushButton("New Recurring Invoice")
        self._new_btn.clicked.connect(self.new_recurring_invoice_requested)
        toolbar_layout.addWidget(self._new_btn)

        layout.addWidget(toolbar_widget)

        # --- Offline banner ---
        self._offline_label = QLabel("Server offline — showing cached data")
        self._offline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._offline_label.setStyleSheet(
            "background: #fff3cd; color: #856404; padding: 4px;"
        )
        self._offline_label.setVisible(False)
        layout.addWidget(self._offline_label)

        # --- Table ---
        self._model = QStandardItemModel(0, len(_COLUMNS))
        self._model.setHorizontalHeaderLabels(_COLUMNS)

        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setStretchLastSection(True)

        self._table.doubleClicked.connect(self._on_double_click)
        self._table.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )
        layout.addWidget(self._table)

        # --- Load more button ---
        self._load_more_btn = QPushButton("Load more")
        self._load_more_btn.clicked.connect(self._on_load_more)
        layout.addWidget(self._load_more_btn)

        self._load_recurring_invoices(reset=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Re-fetch from page 1, respecting current filter state."""
        self._load_recurring_invoices(reset=True)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _active_status_filter(self) -> str | None:
        text = self._status_combo.currentText()
        return None if text == "All" else text.lower()

    def _selected_id(self) -> str | None:
        """Return the recurring invoice id for the currently selected row, or None."""
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        row = indexes[0].row()
        id_item = self._model.item(row, _COL_NAME)
        if id_item is None:
            return None
        return id_item.data(Qt.ItemDataRole.UserRole) or None

    def _load_recurring_invoices(self, reset: bool = False) -> None:
        if reset:
            self._current_page = 1
            self._model.removeRows(0, self._model.rowCount())
            self._has_more = True

        self._offline_label.setVisible(False)
        try:
            items = list_recurring_invoices(
                self._client,
                page=self._current_page,
                page_size=_PAGE_SIZE,
                status_filter=self._active_status_filter(),
            )
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._offline_label.setVisible(True)
            return

        self._append_rows(items)

        if len(items) < _PAGE_SIZE:
            self._has_more = False

        self._load_more_btn.setEnabled(self._has_more)

    def _append_rows(self, recurring_invoices: list[dict[str, Any]]) -> None:
        for ri in recurring_invoices:
            row = self._model.rowCount()
            self._model.insertRow(row)

            name_item = QStandardItem(ri.get("name") or "")
            self._model.setItem(row, _COL_NAME, name_item)

            self._model.setItem(
                row,
                _COL_CONTACT,
                QStandardItem(ri.get("contact_name") or ri.get("contact") or ""),
            )
            self._model.setItem(
                row, _COL_FREQUENCY, QStandardItem(ri.get("frequency") or "")
            )
            self._model.setItem(
                row, _COL_NEXT_DATE, QStandardItem(ri.get("next_date") or "")
            )
            self._model.setItem(
                row, _COL_STATUS, QStandardItem(ri.get("status") or "")
            )

            # Store the recurring invoice id for double-click signal
            name_item.setData(ri.get("id") or "", Qt.ItemDataRole.UserRole)

    def _on_filter_changed(self) -> None:
        self._load_recurring_invoices(reset=True)

    def _on_load_more(self) -> None:
        if not self._has_more:
            return
        self._current_page += 1
        self._load_recurring_invoices(reset=False)

    def _on_double_click(self, index: object) -> None:
        row = index.row()  # type: ignore[union-attr]
        id_item = self._model.item(row, _COL_NAME)
        if id_item is not None:
            ri_id = id_item.data(Qt.ItemDataRole.UserRole)
            if ri_id:
                self.recurring_invoice_selected.emit(str(ri_id))

    def _on_selection_changed(self) -> None:
        self._run_now_btn.setEnabled(bool(self._selected_id()))

    def _on_run_now_clicked(self) -> None:
        ri_id = self._selected_id()
        if not ri_id:
            return
        try:
            run_recurring_invoice(self._client, ri_id)
        except (APIError, ServerOfflineError) as exc:
            QMessageBox.critical(self, "Run failed", str(exc))
            return
        self._offline_label.setText("Invoice generated successfully.")
        self._offline_label.setStyleSheet(
            "background: #e8f5e9; color: #2e7d32; padding: 4px;"
        )
        self._offline_label.setVisible(True)
