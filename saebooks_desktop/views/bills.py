"""Bills list view (Accounts Payable).

Mirror of the Invoices view for the AP side.

Columns: Number | Supplier | Bill Date | Due Date | Amount | Status

Status colours match Invoices:
  - DRAFT  → grey   (#888888)
  - POSTED → green  (#2e7d32)
  - VOIDED → red    (#c62828)

Filter toolbar:
  - Status QComboBox  (All / Draft / Posted / Voided)
  - Date range pair   (QDateEdit  "From" … "To")
  - "New Bill" QPushButton  (emits ``new_bill_requested``)

Signals:
  - ``bill_selected(str)``  — emitted on double-click with the bill id.
  - ``new_bill_requested()`` — emitted when "New Bill" is clicked.

Pagination: "Load more" button appends the next page.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.invoices import list_bills

# Column indices
_COL_NUMBER = 0
_COL_SUPPLIER = 1
_COL_BILL_DATE = 2
_COL_DUE_DATE = 3
_COL_AMOUNT = 4
_COL_STATUS = 5

_COLUMNS = ["Number", "Supplier", "Bill Date", "Due Date", "Amount", "Status"]

# Status colours (foreground)
_STATUS_COLORS: dict[str, QColor] = {
    "draft": QColor("#888888"),
    "posted": QColor("#2e7d32"),
    "voided": QColor("#c62828"),
}

_STATUS_OPTIONS = ["All", "Draft", "Posted", "Voided"]

_PAGE_SIZE = 50


class _StatusDelegate(QStyledItemDelegate):
    """Render the Status column with a coloured foreground."""

    def initStyleOption(
        self, option: QStyleOptionViewItem, index: object
    ) -> None:
        super().initStyleOption(option, index)  # type: ignore[arg-type]
        raw = index.data(Qt.ItemDataRole.DisplayRole) or ""  # type: ignore[union-attr]
        colour = _STATUS_COLORS.get(raw.lower())
        if colour:
            option.palette.setColor(option.palette.ColorRole.Text, colour)  # type: ignore[union-attr]


class BillsView(QWidget):
    """Bills list view.

    Fetches from ``/api/v1/bills`` via REST and renders a filterable,
    paginated table.  Emits ``bill_selected(id)`` on double-click.
    """

    bill_selected = Signal(str)
    new_bill_requested = Signal()

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

        toolbar_layout.addWidget(QLabel("From:"))
        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setSpecialValueText("Any")
        self._date_from.setMinimumDate(self._date_from.minimumDate())
        self._date_from.setDate(self._date_from.minimumDate())
        self._date_from.dateChanged.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self._date_from)

        toolbar_layout.addWidget(QLabel("To:"))
        self._date_to = QDateEdit()
        self._date_to.setCalendarPopup(True)
        self._date_to.setSpecialValueText("Any")
        self._date_to.setMinimumDate(self._date_to.minimumDate())
        self._date_to.setDate(self._date_to.minimumDate())
        self._date_to.dateChanged.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self._date_to)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        toolbar_layout.addWidget(spacer)

        self._new_btn = QPushButton("New Bill")
        self._new_btn.clicked.connect(self.new_bill_requested)
        toolbar_layout.addWidget(self._new_btn)

        self._export_btn = QPushButton("Export CSV")
        self._export_btn.clicked.connect(self._on_export_clicked)
        toolbar_layout.addWidget(self._export_btn)

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

        # Right-align the Amount column header and cells
        self._model.horizontalHeaderItem(_COL_AMOUNT).setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        # Coloured status delegate
        self._table.setItemDelegateForColumn(_COL_STATUS, _StatusDelegate(self._table))

        self._table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        # --- Load more button ---
        self._load_more_btn = QPushButton("Load more")
        self._load_more_btn.clicked.connect(self._on_load_more)
        layout.addWidget(self._load_more_btn)

        self._load_bills(reset=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Re-fetch from page 1, respecting current filter state."""
        self._load_bills(reset=True)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _active_status_filter(self) -> str | None:
        text = self._status_combo.currentText()
        return None if text == "All" else text.lower()

    def _active_date_from(self) -> str | None:
        d = self._date_from.date()
        if d == self._date_from.minimumDate():
            return None
        return d.toString("yyyy-MM-dd")

    def _active_date_to(self) -> str | None:
        d = self._date_to.date()
        if d == self._date_to.minimumDate():
            return None
        return d.toString("yyyy-MM-dd")

    def _load_bills(self, reset: bool = False) -> None:
        if reset:
            self._current_page = 1
            self._model.removeRows(0, self._model.rowCount())
            self._has_more = True

        self._offline_label.setVisible(False)
        try:
            items = list_bills(
                self._client,
                page=self._current_page,
                page_size=_PAGE_SIZE,
                status_filter=self._active_status_filter(),
                date_from=self._active_date_from(),
                date_to=self._active_date_to(),
            )
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._offline_label.setVisible(True)
            return

        self._append_rows(items)

        if len(items) < _PAGE_SIZE:
            self._has_more = False

        self._load_more_btn.setEnabled(self._has_more)

    def _append_rows(self, bills: list[dict[str, Any]]) -> None:
        for bill in bills:
            row = self._model.rowCount()
            self._model.insertRow(row)

            self._model.setItem(row, _COL_NUMBER, QStandardItem(bill.get("number") or ""))
            self._model.setItem(row, _COL_SUPPLIER, QStandardItem(bill.get("supplier_name") or bill.get("supplier") or ""))
            self._model.setItem(row, _COL_BILL_DATE, QStandardItem(bill.get("bill_date") or bill.get("issue_date") or ""))
            self._model.setItem(row, _COL_DUE_DATE, QStandardItem(bill.get("due_date") or ""))

            amount_item = QStandardItem(bill.get("amount") or bill.get("total") or "")
            amount_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._model.setItem(row, _COL_AMOUNT, amount_item)

            self._model.setItem(row, _COL_STATUS, QStandardItem(bill.get("status") or ""))

            # Store the bill id for double-click signal
            self._model.item(row, _COL_NUMBER).setData(bill.get("id") or "", Qt.ItemDataRole.UserRole)

    def _on_filter_changed(self) -> None:
        self._load_bills(reset=True)

    def _on_load_more(self) -> None:
        if not self._has_more:
            return
        self._current_page += 1
        self._load_bills(reset=False)

    def _on_double_click(self, index: object) -> None:
        row = index.row()  # type: ignore[union-attr]
        id_item = self._model.item(row, _COL_NUMBER)
        if id_item is not None:
            bill_id = id_item.data(Qt.ItemDataRole.UserRole)
            if bill_id:
                self.bill_selected.emit(str(bill_id))

    def _on_export_clicked(self) -> None:
        """Export the current model to CSV via a save dialog."""
        from PySide6.QtWidgets import QMessageBox

        from saebooks_desktop.services.csv_export import ensure_csv_path, export_model_to_csv

        path = ensure_csv_path(self, "bills")
        if path is None:
            return
        try:
            n = export_model_to_csv(self._model, path)
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", f"Could not write CSV:\n{exc}")
            return
        self._offline_label.setText(f"Exported {n} rows to {path.split('/')[-1]}")
        self._offline_label.setStyleSheet("background: #e8f5e9; color: #2e7d32; padding: 4px;")
        self._offline_label.setVisible(True)
