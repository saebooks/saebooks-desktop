"""Invoice detail view — read-only display of a single invoice.

Opened when the user double-clicks a row in InvoicesView.

Layout:
  - Header: invoice number (bold/large), status badge, contact name,
    issue date, due date
  - Lines table (QTableView): Description | Account | Qty | Unit Price |
    Tax Code | Amount  (Amount right-aligned)
  - Totals section: Subtotal, Tax, Total (right-aligned; Total larger font)
  - Action toolbar: Edit (disabled), Void (disabled for draft/voided;
    confirm dialog before emit), Back
  - Offline banner

Signals:
  - ``edit_requested(str)``  — invoice id (Edit button; currently disabled)
  - ``void_requested(str)``  — invoice id (after user confirms)
  - ``back_requested()``     — Back button
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
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

from saebooks_desktop.services.api_client import APIClient, APIError, ServerOfflineError
from saebooks_desktop.services.invoice_detail import get_invoice
from saebooks_desktop.services.stripe_links import generate_payment_link

# Lines table column indices
_COL_DESC = 0
_COL_ACCOUNT = 1
_COL_QTY = 2
_COL_UNIT_PRICE = 3
_COL_TAX_CODE = 4
_COL_AMOUNT = 5

_LINE_COLUMNS = ["Description", "Account", "Qty", "Unit Price", "Tax Code", "Amount"]

# Status colours — matches InvoicesView delegate
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


class InvoiceDetailView(QWidget):
    """Read-only detail view for a single invoice.

    Call ``load(invoice_id)`` to populate.  The constructor wires up all
    widgets but leaves them empty until load() is called.
    """

    edit_requested = Signal(str)
    void_requested = Signal(str)
    payment_requested = Signal(str)
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._client = APIClient()
        self._invoice_id: str = ""
        self._invoice_status: str = ""

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

        # Row 2: contact, issue date, due date
        meta_row = QWidget()
        meta_layout = QHBoxLayout(meta_row)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(24)

        self._contact_label = QLabel()
        meta_layout.addWidget(QLabel("Contact:"))
        meta_layout.addWidget(self._contact_label)

        meta_layout.addWidget(QLabel("Issue Date:"))
        self._issue_date_label = QLabel()
        meta_layout.addWidget(self._issue_date_label)

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

        # Right-align numeric columns
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

        self._record_payment_btn = QPushButton("Record Payment")
        self._record_payment_btn.setEnabled(False)
        self._record_payment_btn.clicked.connect(self._on_record_payment_clicked)
        toolbar_layout.addWidget(self._record_payment_btn)

        self._payment_link_btn = QPushButton("Generate Payment Link")
        self._payment_link_btn.setEnabled(False)
        self._payment_link_btn.clicked.connect(self._on_payment_link_clicked)
        toolbar_layout.addWidget(self._payment_link_btn)

        # Inline error banner for payment link failures (hidden until needed)
        self._payment_link_error = QLabel()
        self._payment_link_error.setWordWrap(True)
        self._payment_link_error.setStyleSheet(
            "background: #fff3cd; color: #856404; padding: 4px; border-radius: 4px;"
        )
        self._payment_link_error.setVisible(False)
        layout.addWidget(self._payment_link_error)

        self._back_btn = QPushButton("Back")
        self._back_btn.clicked.connect(self.back_requested)
        toolbar_layout.addWidget(self._back_btn)

        layout.addWidget(toolbar)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, invoice_id: str) -> None:
        """Fetch and display the invoice identified by *invoice_id*."""
        self._invoice_id = invoice_id
        self._offline_label.setVisible(False)

        try:
            data = get_invoice(self._client, invoice_id)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._offline_label.setVisible(True)
            return

        self._populate(data)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _populate(self, data: dict[str, Any]) -> None:
        self._invoice_status = (data.get("status") or "").lower()

        # Header
        self._number_label.setText(data.get("number") or "")
        self._set_status_badge(self._invoice_status)
        self._contact_label.setText(
            data.get("contact_name") or str(data.get("contact_id") or "")
        )
        self._issue_date_label.setText(str(data.get("issue_date") or ""))
        self._due_date_label.setText(str(data.get("due_date") or ""))

        # Lines
        self._lines_model.removeRows(0, self._lines_model.rowCount())
        for line in data.get("lines") or []:
            self._append_line(line)

        # Totals
        self._subtotal_label.setText(_fmt(data.get("subtotal")))
        self._tax_label.setText(_fmt(data.get("tax_total")))
        self._total_label.setText(_fmt(data.get("total")))

        # Void button: enabled only for POSTED invoices
        self._void_btn.setEnabled(self._invoice_status == "posted")
        # Record Payment: enabled only for POSTED invoices
        self._record_payment_btn.setEnabled(self._invoice_status == "posted")
        # Generate Payment Link: enabled only for POSTED invoices
        self._payment_link_btn.setEnabled(self._invoice_status == "posted")
        # Clear any stale error banner from a previous load
        self._payment_link_error.setVisible(False)

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
        # Light background tint for badge
        r, g, b = bg.red(), bg.green(), bg.blue()
        self._status_badge.setStyleSheet(
            f"border-radius: 4px; padding: 2px 8px; font-weight: bold;"
            f" background: rgba({r},{g},{b},30); color: {colour};"
        )

    def _on_edit_clicked(self) -> None:
        if self._invoice_id:
            self.edit_requested.emit(self._invoice_id)

    def _on_record_payment_clicked(self) -> None:
        if self._invoice_id:
            self.payment_requested.emit(self._invoice_id)

    def _on_void_clicked(self) -> None:
        if not self._invoice_id:
            return
        reply = QMessageBox.question(
            self,
            "Void Invoice",
            "Are you sure you want to void this invoice? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.void_requested.emit(self._invoice_id)

    def _on_payment_link_clicked(self) -> None:
        """Generate a Stripe payment link and show it in a dialog."""
        if not self._invoice_id:
            return

        self._payment_link_error.setVisible(False)

        try:
            url = generate_payment_link(self._client, self._invoice_id)
        except APIError as exc:
            if exc.status_code == 503:
                self._payment_link_error.setText(
                    "Stripe not configured — add STRIPE_SECRET_KEY to server config."
                )
            elif exc.status_code == 422:
                self._payment_link_error.setText(
                    "Invoice must be posted with an outstanding balance."
                )
            else:
                self._payment_link_error.setText(
                    f"Could not generate payment link: {exc}"
                )
            self._payment_link_error.setVisible(True)
            return
        except ServerOfflineError as exc:
            self._payment_link_error.setText(f"Server offline: {exc}")
            self._payment_link_error.setVisible(True)
            return

        # Success — show dialog with URL and copy button
        dlg = _PaymentLinkDialog(url, parent=self)
        dlg.exec()


# ---------------------------------------------------------------------------
# Payment link dialog
# ---------------------------------------------------------------------------


class _PaymentLinkDialog(QDialog):
    """Simple dialog that displays a Stripe payment link URL with a Copy button."""

    def __init__(self, url: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Stripe Payment Link")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Payment link generated:"))

        url_label = QLabel(url)
        url_label.setWordWrap(True)
        url_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        layout.addWidget(url_label)

        btn_box = QDialogButtonBox()
        copy_btn = QPushButton("Copy to clipboard")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(url))
        btn_box.addButton(copy_btn, QDialogButtonBox.ButtonRole.ActionRole)
        btn_box.addButton(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.accept)
        layout.addWidget(btn_box)


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
