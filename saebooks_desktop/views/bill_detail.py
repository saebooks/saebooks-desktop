"""Bill detail view — read-only display of a single bill (AP).

Mirror of InvoiceDetailView for the Accounts Payable side.
Uses supplier name instead of customer contact name.

Signals:
  - ``edit_requested(str)``  — bill id (Edit button; currently disabled)
  - ``void_requested(str)``  — bill id (after user confirms)
  - ``back_requested()``     — Back button
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.bill_detail import get_bill

# Lines table column indices
_COL_DESC = 0
_COL_ACCOUNT = 1
_COL_QTY = 2
_COL_UNIT_PRICE = 3
_COL_TAX_CODE = 4
_COL_AMOUNT = 5

_LINE_COLUMNS = ["Description", "Account", "Qty", "Unit Price", "Tax Code", "Amount"]

# Status colours — matches BillsView delegate
_STATUS_COLORS: dict[str, str] = {
    "draft": "#888888",
    "posted": "#2e7d32",
    "voided": "#c62828",
}


class _RightAlignDelegate(QStyledItemDelegate):
    """Right-align numeric columns."""

    def initStyleOption(self, option: QStyleOptionViewItem, index: object) -> None:
        super().initStyleOption(option, index)  # type: ignore[arg-type]
        option.displayAlignment = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter  # type: ignore[union-attr]


class BillDetailView(QWidget):
    """Read-only detail view for a single bill.

    Call ``load(bill_id)`` to populate.
    """

    edit_requested = Signal(str)
    void_requested = Signal(str)
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._client = APIClient()
        self._bill_id: str = ""
        self._bill_status: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # --- Offline banner ---
        self._offline_label = QLabel("Server offline — showing cached data")
        self._offline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._offline_label.setStyleSheet(
            "background: #fff3cd; color: #856404; padding: 4px;"
        )
        self._offline_label.setVisible(False)
        layout.addWidget(self._offline_label)

        # --- Header section ---
        header_frame = QFrame()
        header_frame.setFrameShape(QFrame.Shape.StyledPanel)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setSpacing(4)

        # Row 1: number + status badge
        top_row = QWidget()
        top_row_layout = QHBoxLayout(top_row)
        top_row_layout.setContentsMargins(0, 0, 0, 0)

        self._number_label = QLabel()
        number_font = QFont()
        number_font.setBold(True)
        number_font.setPointSize(16)
        self._number_label.setFont(number_font)
        top_row_layout.addWidget(self._number_label)

        self._status_badge = QLabel()
        self._status_badge.setFixedHeight(24)
        self._status_badge.setAlignment(
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
        )
        self._status_badge.setStyleSheet(
            "border-radius: 4px; padding: 2px 8px; font-weight: bold;"
        )
        top_row_layout.addWidget(self._status_badge)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        top_row_layout.addWidget(spacer)
        header_layout.addWidget(top_row)

        # Row 2: supplier, bill date, due date
        meta_row = QWidget()
        meta_layout = QHBoxLayout(meta_row)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(24)

        meta_layout.addWidget(QLabel("Supplier:"))
        self._supplier_label = QLabel()
        meta_layout.addWidget(self._supplier_label)

        meta_layout.addWidget(QLabel("Bill Date:"))
        self._bill_date_label = QLabel()
        meta_layout.addWidget(self._bill_date_label)

        meta_layout.addWidget(QLabel("Due Date:"))
        self._due_date_label = QLabel()
        meta_layout.addWidget(self._due_date_label)

        spacer2 = QWidget()
        spacer2.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        meta_layout.addWidget(spacer2)
        header_layout.addWidget(meta_row)
        layout.addWidget(header_frame)

        # --- Lines table ---
        self._lines_model = QStandardItemModel(0, len(_LINE_COLUMNS))
        self._lines_model.setHorizontalHeaderLabels(_LINE_COLUMNS)

        self._lines_table = QTableView()
        self._lines_table.setModel(self._lines_model)
        self._lines_table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._lines_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._lines_table.horizontalHeader().setStretchLastSection(True)

        _right = _RightAlignDelegate(self._lines_table)
        self._lines_table.setItemDelegateForColumn(_COL_QTY, _right)
        self._lines_table.setItemDelegateForColumn(_COL_UNIT_PRICE, _right)
        self._lines_table.setItemDelegateForColumn(_COL_AMOUNT, _right)
        layout.addWidget(self._lines_table, 1)

        # --- Totals section ---
        totals_frame = QFrame()
        totals_layout = QVBoxLayout(totals_frame)
        totals_layout.setSpacing(4)

        self._subtotal_label = _right_label("")
        self._tax_label = _right_label("")
        self._total_label = _right_label("")
        total_font = QFont()
        total_font.setBold(True)
        total_font.setPointSize(13)
        self._total_label.setFont(total_font)

        totals_layout.addWidget(_labeled_row("Subtotal:", self._subtotal_label))
        totals_layout.addWidget(_labeled_row("Tax:", self._tax_label))

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        totals_layout.addWidget(sep)

        totals_layout.addWidget(_labeled_row("Total:", self._total_label))
        layout.addWidget(totals_frame)

        # --- Action toolbar ---
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 4, 0, 0)

        toolbar_spacer = QWidget()
        toolbar_spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        toolbar_layout.addWidget(toolbar_spacer)

        self._edit_btn = QPushButton("Edit")
        self._edit_btn.setEnabled(False)  # E/12+
        self._edit_btn.clicked.connect(self._on_edit_clicked)
        toolbar_layout.addWidget(self._edit_btn)

        self._void_btn = QPushButton("Void")
        self._void_btn.setEnabled(False)
        self._void_btn.clicked.connect(self._on_void_clicked)
        toolbar_layout.addWidget(self._void_btn)

        self._back_btn = QPushButton("Back")
        self._back_btn.clicked.connect(self.back_requested)
        toolbar_layout.addWidget(self._back_btn)

        layout.addWidget(toolbar)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, bill_id: str) -> None:
        """Fetch and display the bill identified by *bill_id*."""
        self._bill_id = bill_id
        self._offline_label.setVisible(False)

        try:
            data = get_bill(self._client, bill_id)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._offline_label.setVisible(True)
            return

        self._populate(data)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _populate(self, data: dict[str, Any]) -> None:
        self._bill_status = (data.get("status") or "").lower()

        # Header
        self._number_label.setText(data.get("number") or "")
        self._set_status_badge(self._bill_status)
        self._supplier_label.setText(
            data.get("supplier_name") or str(data.get("contact_id") or "")
        )
        self._bill_date_label.setText(str(data.get("issue_date") or ""))
        self._due_date_label.setText(str(data.get("due_date") or ""))

        # Lines
        self._lines_model.removeRows(0, self._lines_model.rowCount())
        for line in data.get("lines") or []:
            self._append_line(line)

        # Totals
        self._subtotal_label.setText(_fmt(data.get("subtotal")))
        self._tax_label.setText(_fmt(data.get("tax_total")))
        self._total_label.setText(_fmt(data.get("total")))

        # Void button: enabled only for POSTED bills
        self._void_btn.setEnabled(self._bill_status == "posted")

    def _append_line(self, line: dict[str, Any]) -> None:
        row = self._lines_model.rowCount()
        self._lines_model.insertRow(row)

        self._lines_model.setItem(row, _COL_DESC, QStandardItem(line.get("description") or ""))
        self._lines_model.setItem(row, _COL_ACCOUNT, QStandardItem(str(line.get("account_id") or "")))
        self._lines_model.setItem(row, _COL_QTY, _num_item(line.get("quantity")))
        self._lines_model.setItem(row, _COL_UNIT_PRICE, _num_item(line.get("unit_price")))
        tax_code = str(line.get("tax_code_id") or "")
        self._lines_model.setItem(row, _COL_TAX_CODE, QStandardItem(tax_code))
        self._lines_model.setItem(row, _COL_AMOUNT, _num_item(line.get("line_total")))

    def _set_status_badge(self, status: str) -> None:
        colour = _STATUS_COLORS.get(status, "#888888")
        self._status_badge.setText(status.upper() if status else "")
        bg = QColor(colour)
        r, g, b = bg.red(), bg.green(), bg.blue()
        self._status_badge.setStyleSheet(
            f"border-radius: 4px; padding: 2px 8px; font-weight: bold;"
            f" background: rgba({r},{g},{b},30); color: {colour};"
        )

    def _on_edit_clicked(self) -> None:
        if self._bill_id:
            self.edit_requested.emit(self._bill_id)

    def _on_void_clicked(self) -> None:
        if not self._bill_id:
            return
        reply = QMessageBox.question(
            self,
            "Void Bill",
            "Are you sure you want to void this bill? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.void_requested.emit(self._bill_id)


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


def _right_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return lbl


def _labeled_row(label_text: str, value_widget: QLabel) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    spacer = QWidget()
    spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    layout.addWidget(spacer)
    layout.addWidget(QLabel(label_text))
    layout.addWidget(value_widget)
    return row


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _num_item(value: Any) -> QStandardItem:
    item = QStandardItem(_fmt(value))
    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return item
