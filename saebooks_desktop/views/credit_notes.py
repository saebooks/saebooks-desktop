"""Credit Notes views — list and form.

``CreditNotesView``
    Filterable, paginated QTableView of credit notes fetched from
    ``GET /api/v1/credit_notes``.

    Columns: Number | Contact | Date | Total | Status

    Signals:
        credit_note_selected(str)    — emitted on double-click with the credit note id.
        new_credit_note_requested()  — emitted when "New Credit Note" is clicked.

``CreditNoteForm``
    Create/edit form for a single credit note.  Similar shape to InvoiceForm
    but targets the credit note endpoints and uses ``date`` (not ``issue_date``).

    Signals:
        credit_note_saved(str)       — emitted with the saved credit note id.
        cancelled()                  — emitted when Cancel is clicked.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor, QFont, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.credit_notes import (
    create_credit_note,
    get_credit_note,
    list_contacts_for_credit_note,
    list_credit_notes,
    list_income_accounts_for_credit_note,
    list_tax_codes_for_credit_note,
    post_credit_note,
    update_credit_note,
)

# ---------------------------------------------------------------------------
# List view constants
# ---------------------------------------------------------------------------

_COL_NUMBER = 0
_COL_CONTACT = 1
_COL_DATE = 2
_COL_TOTAL = 3
_COL_STATUS = 4

_COLUMNS = ["Number", "Contact", "Date", "Total", "Status"]

_STATUS_COLORS: dict[str, QColor] = {
    "draft": QColor("#888888"),
    "posted": QColor("#2e7d32"),
    "voided": QColor("#c62828"),
}

_STATUS_OPTIONS = ["All", "Draft", "Posted", "Voided"]

_PAGE_SIZE = 50

# ---------------------------------------------------------------------------
# Form line-items table constants
# ---------------------------------------------------------------------------

_FORM_COL_DESC = 0
_FORM_COL_ACCOUNT = 1
_FORM_COL_QTY = 2
_FORM_COL_UNIT_PRICE = 3
_FORM_COL_TAX_CODE = 4
_FORM_COL_AMOUNT = 5
_FORM_COL_REMOVE = 6

_FORM_LINE_COLUMNS = ["Description", "Account", "Qty", "Unit Price", "Tax Code", "Amount", ""]


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


class CreditNotesView(QWidget):
    """Credit notes list view.

    Fetches from ``/api/v1/credit_notes`` via REST and renders a filterable,
    paginated table.  Emits ``credit_note_selected(id)`` on double-click.
    """

    credit_note_selected = Signal(str)
    new_credit_note_requested = Signal()

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

        self._new_btn = QPushButton("New Credit Note")
        self._new_btn.clicked.connect(self.new_credit_note_requested)
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

        self._model.horizontalHeaderItem(_COL_TOTAL).setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        self._table.setItemDelegateForColumn(_COL_STATUS, _StatusDelegate(self._table))
        self._table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        # --- Load more button ---
        self._load_more_btn = QPushButton("Load more")
        self._load_more_btn.clicked.connect(self._on_load_more)
        layout.addWidget(self._load_more_btn)

        self._load_credit_notes(reset=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Re-fetch from page 1, respecting current filter state."""
        self._load_credit_notes(reset=True)

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

    def _load_credit_notes(self, reset: bool = False) -> None:
        if reset:
            self._current_page = 1
            self._model.removeRows(0, self._model.rowCount())
            self._has_more = True

        self._offline_label.setVisible(False)
        try:
            items = list_credit_notes(
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

    def _append_rows(self, credit_notes: list[dict[str, Any]]) -> None:
        for cn in credit_notes:
            row = self._model.rowCount()
            self._model.insertRow(row)

            self._model.setItem(row, _COL_NUMBER, QStandardItem(cn.get("number") or ""))
            self._model.setItem(
                row,
                _COL_CONTACT,
                QStandardItem(cn.get("contact_name") or ""),
            )
            self._model.setItem(row, _COL_DATE, QStandardItem(cn.get("date") or ""))

            total_item = QStandardItem(str(cn.get("total") or ""))
            total_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._model.setItem(row, _COL_TOTAL, total_item)

            self._model.setItem(
                row, _COL_STATUS, QStandardItem(cn.get("status") or "")
            )

            # Store the credit note id for double-click signal
            self._model.item(row, _COL_NUMBER).setData(
                cn.get("id") or "", Qt.ItemDataRole.UserRole
            )

    def _on_filter_changed(self) -> None:
        self._load_credit_notes(reset=True)

    def _on_load_more(self) -> None:
        if not self._has_more:
            return
        self._current_page += 1
        self._load_credit_notes(reset=False)

    def _on_double_click(self, index: object) -> None:
        row = index.row()  # type: ignore[union-attr]
        id_item = self._model.item(row, _COL_NUMBER)
        if id_item is not None:
            cn_id = id_item.data(Qt.ItemDataRole.UserRole)
            if cn_id:
                self.credit_note_selected.emit(str(cn_id))


# ---------------------------------------------------------------------------
# Form view
# ---------------------------------------------------------------------------


class CreditNoteForm(QWidget):
    """Create/edit form for a single credit note.

    In create mode (``credit_note_id=None``) the form is blank.
    In edit mode an existing credit note is loaded and fields pre-filled.
    """

    credit_note_saved = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        client: APIClient,
        credit_note_id: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._client = client
        self._credit_note_id = credit_note_id
        self._etag: int | None = None

        # Reference data populated in _load_reference_data()
        self._contacts: list[dict[str, Any]] = []
        self._accounts: list[dict[str, Any]] = []
        self._tax_codes: list[dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # --- Error / offline banner ---
        self._banner = QLabel()
        self._banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._banner.setVisible(False)
        layout.addWidget(self._banner)

        # --- Header section ---
        header_frame = QFrame()
        header_frame.setFrameShape(QFrame.Shape.StyledPanel)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setSpacing(6)

        # Contact row
        contact_row = QWidget()
        contact_row_layout = QHBoxLayout(contact_row)
        contact_row_layout.setContentsMargins(0, 0, 0, 0)
        contact_row_layout.addWidget(QLabel("Contact:"))
        self._contact_combo = QComboBox()
        self._contact_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        contact_row_layout.addWidget(self._contact_combo)
        header_layout.addWidget(contact_row)

        # Number / Reference row
        num_ref_row = QWidget()
        num_ref_layout = QHBoxLayout(num_ref_row)
        num_ref_layout.setContentsMargins(0, 0, 0, 0)
        num_ref_layout.addWidget(QLabel("Credit Note #:"))
        self._number_edit = QLineEdit()
        self._number_edit.setPlaceholderText("Auto-generated")
        num_ref_layout.addWidget(self._number_edit)
        num_ref_layout.addWidget(QLabel("Reference:"))
        self._reference_edit = QLineEdit()
        self._reference_edit.setPlaceholderText("Optional")
        num_ref_layout.addWidget(self._reference_edit)
        header_layout.addWidget(num_ref_row)

        # Date row
        date_row = QWidget()
        date_layout = QHBoxLayout(date_row)
        date_layout.setContentsMargins(0, 0, 0, 0)
        today = QDate.currentDate()
        date_layout.addWidget(QLabel("Date:"))
        self._date_edit = QDateEdit(today)
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        date_layout.addWidget(self._date_edit)
        date_spacer = QWidget()
        date_spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        date_layout.addWidget(date_spacer)
        header_layout.addWidget(date_row)
        layout.addWidget(header_frame)

        # --- Line items table ---
        self._lines_table = QTableWidget(0, len(_FORM_LINE_COLUMNS))
        self._lines_table.setHorizontalHeaderLabels(_FORM_LINE_COLUMNS)
        self._lines_table.horizontalHeader().setStretchLastSection(False)
        self._lines_table.horizontalHeader().setSectionResizeMode(
            _FORM_COL_DESC,
            self._lines_table.horizontalHeader().ResizeMode.Stretch,
        )
        self._lines_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        layout.addWidget(self._lines_table, 1)

        # Add line button
        add_line_row = QWidget()
        add_line_layout = QHBoxLayout(add_line_row)
        add_line_layout.setContentsMargins(0, 0, 0, 0)
        self._add_line_btn = QPushButton("Add Line")
        self._add_line_btn.clicked.connect(self._on_add_line)
        add_line_layout.addWidget(self._add_line_btn)
        add_line_layout.addStretch()
        layout.addWidget(add_line_row)

        # --- Totals section ---
        totals_frame = QFrame()
        totals_layout = QVBoxLayout(totals_frame)
        totals_layout.setSpacing(4)

        self._subtotal_label = _right_label("0.00")
        self._tax_label = _right_label("0.00")
        self._total_label = _right_label("0.00")

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

        self._save_draft_btn = QPushButton("Save as Draft")
        self._save_draft_btn.clicked.connect(self._on_save_draft)
        toolbar_layout.addWidget(self._save_draft_btn)

        self._save_post_btn = QPushButton("Save && Post")
        self._save_post_btn.clicked.connect(self._on_save_post)
        toolbar_layout.addWidget(self._save_post_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.cancelled)
        toolbar_layout.addWidget(self._cancel_btn)

        layout.addWidget(toolbar)

        # Load reference data then optionally the existing credit note
        self._load_reference_data()
        if self._credit_note_id:
            self._load_existing_credit_note()
        else:
            self._append_blank_line()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def line_count(self) -> int:
        """Return the current number of line rows."""
        return self._lines_table.rowCount()

    # ------------------------------------------------------------------
    # Reference data
    # ------------------------------------------------------------------

    def _load_reference_data(self) -> None:
        """Fetch contacts, accounts, and tax codes from the API."""
        try:
            self._contacts = list_contacts_for_credit_note(self._client)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._contacts = []

        try:
            self._accounts = list_income_accounts_for_credit_note(self._client)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._accounts = []

        try:
            self._tax_codes = list_tax_codes_for_credit_note(self._client)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._tax_codes = []

        # Populate contact combo
        self._contact_combo.clear()
        self._contact_combo.addItem("-- Select Contact --", userData=None)
        for c in self._contacts:
            self._contact_combo.addItem(
                c.get("name") or str(c.get("id", "")), userData=c.get("id")
            )

    # ------------------------------------------------------------------
    # Edit mode — load existing credit note
    # ------------------------------------------------------------------

    def _load_existing_credit_note(self) -> None:
        """Fetch existing credit note and pre-fill form fields."""
        assert self._credit_note_id is not None
        try:
            data = get_credit_note(self._client, self._credit_note_id)
        except (ServerOfflineError, Exception) as exc:  # noqa: BLE001
            self._show_banner(f"Could not load credit note: {exc}", error=True)
            self._append_blank_line()
            return

        self._etag = data.get("version")

        # Contact
        contact_id = str(data.get("contact_id") or "")
        idx = self._contact_combo.findData(contact_id)
        if idx >= 0:
            self._contact_combo.setCurrentIndex(idx)

        # Number / reference
        self._number_edit.setText(data.get("number") or "")
        self._reference_edit.setText(data.get("reference") or "")

        # Date
        if data.get("date"):
            self._date_edit.setDate(
                QDate.fromString(str(data["date"]), "yyyy-MM-dd")
            )

        # Lines
        lines = data.get("lines") or []
        if lines:
            for line in lines:
                self._append_line_from_data(line)
        else:
            self._append_blank_line()

        self._recalculate_totals()

    # ------------------------------------------------------------------
    # Line table helpers
    # ------------------------------------------------------------------

    def _append_blank_line(self) -> None:
        row = self._lines_table.rowCount()
        self._lines_table.insertRow(row)
        self._populate_line_row(row, {})

    def _append_line_from_data(self, line: dict[str, Any]) -> None:
        row = self._lines_table.rowCount()
        self._lines_table.insertRow(row)
        self._populate_line_row(row, line)

    def _populate_line_row(self, row: int, line: dict[str, Any]) -> None:
        # Description
        desc_edit = QLineEdit(line.get("description") or "")
        self._lines_table.setCellWidget(row, _FORM_COL_DESC, desc_edit)

        # Account combo
        account_combo = QComboBox()
        account_combo.addItem("-- Account --", userData=None)
        for acc in self._accounts:
            account_combo.addItem(
                acc.get("name") or str(acc.get("id", "")), userData=acc.get("id")
            )
        acc_id = str(line.get("account_id") or "")
        acc_idx = account_combo.findData(acc_id)
        if acc_idx >= 0:
            account_combo.setCurrentIndex(acc_idx)
        self._lines_table.setCellWidget(row, _FORM_COL_ACCOUNT, account_combo)

        # Qty
        qty_spin = QDoubleSpinBox()
        qty_spin.setDecimals(2)
        qty_spin.setMinimum(0.0)
        qty_spin.setMaximum(9_999_999.99)
        qty_spin.setValue(float(line.get("quantity") or 0.0))
        qty_spin.valueChanged.connect(lambda _, r=row: self._on_line_changed(r))
        self._lines_table.setCellWidget(row, _FORM_COL_QTY, qty_spin)

        # Unit price
        price_spin = QDoubleSpinBox()
        price_spin.setDecimals(2)
        price_spin.setMinimum(0.0)
        price_spin.setMaximum(9_999_999.99)
        price_spin.setValue(float(line.get("unit_price") or 0.0))
        price_spin.valueChanged.connect(lambda _, r=row: self._on_line_changed(r))
        self._lines_table.setCellWidget(row, _FORM_COL_UNIT_PRICE, price_spin)

        # Tax code combo
        tax_combo = QComboBox()
        tax_combo.addItem("-- No Tax --", userData=None)
        for tc in self._tax_codes:
            label = tc.get("code") or str(tc.get("id", ""))
            tax_combo.addItem(label, userData=tc.get("id"))
        tc_id = str(line.get("tax_code_id") or "")
        tc_idx = tax_combo.findData(tc_id)
        if tc_idx >= 0:
            tax_combo.setCurrentIndex(tc_idx)
        tax_combo.currentIndexChanged.connect(lambda _, r=row: self._on_line_changed(r))
        self._lines_table.setCellWidget(row, _FORM_COL_TAX_CODE, tax_combo)

        # Amount (read-only)
        amount_item = QTableWidgetItem("0.00")
        amount_item.setFlags(amount_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        amount_item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._lines_table.setItem(row, _FORM_COL_AMOUNT, amount_item)

        # Remove button
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(lambda _, r=row: self._on_remove_line(r))
        self._lines_table.setCellWidget(row, _FORM_COL_REMOVE, remove_btn)

        self._update_line_amount(row)

    def _on_add_line(self) -> None:
        self._append_blank_line()
        self._recalculate_totals()

    def _on_remove_line(self, row: int) -> None:
        if self._lines_table.rowCount() <= 1:
            return
        self._lines_table.removeRow(row)
        self._rewire_remove_buttons()
        self._recalculate_totals()

    def _rewire_remove_buttons(self) -> None:
        for r in range(self._lines_table.rowCount()):
            btn = self._lines_table.cellWidget(r, _FORM_COL_REMOVE)
            if btn is not None:
                try:
                    btn.clicked.disconnect()
                except RuntimeError:
                    pass
                btn.clicked.connect(lambda _, row=r: self._on_remove_line(row))
            qty_w = self._lines_table.cellWidget(r, _FORM_COL_QTY)
            price_w = self._lines_table.cellWidget(r, _FORM_COL_UNIT_PRICE)
            tax_w = self._lines_table.cellWidget(r, _FORM_COL_TAX_CODE)
            if qty_w is not None:
                try:
                    qty_w.valueChanged.disconnect()
                except RuntimeError:
                    pass
                qty_w.valueChanged.connect(lambda _, row=r: self._on_line_changed(row))
            if price_w is not None:
                try:
                    price_w.valueChanged.disconnect()
                except RuntimeError:
                    pass
                price_w.valueChanged.connect(
                    lambda _, row=r: self._on_line_changed(row)
                )
            if tax_w is not None:
                try:
                    tax_w.currentIndexChanged.disconnect()
                except RuntimeError:
                    pass
                tax_w.currentIndexChanged.connect(
                    lambda _, row=r: self._on_line_changed(row)
                )

    def _on_line_changed(self, row: int) -> None:
        self._update_line_amount(row)
        self._recalculate_totals()

    def _update_line_amount(self, row: int) -> None:
        qty_w = self._lines_table.cellWidget(row, _FORM_COL_QTY)
        price_w = self._lines_table.cellWidget(row, _FORM_COL_UNIT_PRICE)
        if qty_w is None or price_w is None:
            return
        amount = qty_w.value() * price_w.value()
        item = self._lines_table.item(row, _FORM_COL_AMOUNT)
        if item is not None:
            item.setText(f"{amount:.2f}")

    def _recalculate_totals(self) -> None:
        subtotal = 0.0
        tax_total = 0.0
        for row in range(self._lines_table.rowCount()):
            qty_w = self._lines_table.cellWidget(row, _FORM_COL_QTY)
            price_w = self._lines_table.cellWidget(row, _FORM_COL_UNIT_PRICE)
            tax_w = self._lines_table.cellWidget(row, _FORM_COL_TAX_CODE)
            if qty_w is None or price_w is None:
                continue
            line_amount = qty_w.value() * price_w.value()
            subtotal += line_amount
            if tax_w is not None:
                tc_id = tax_w.currentData()
                if tc_id is not None:
                    rate = self._tax_rate_for_id(tc_id)
                    tax_total += line_amount * rate
        total = subtotal + tax_total
        self._subtotal_label.setText(f"{subtotal:.2f}")
        self._tax_label.setText(f"{tax_total:.2f}")
        self._total_label.setText(f"{total:.2f}")

    def _tax_rate_for_id(self, tc_id: Any) -> float:
        for tc in self._tax_codes:
            if str(tc.get("id", "")) == str(tc_id):
                raw = tc.get("rate", 0)
                try:
                    return float(raw)
                except (TypeError, ValueError):
                    return 0.0
        return 0.0

    # ------------------------------------------------------------------
    # Build payload
    # ------------------------------------------------------------------

    def _build_payload(self, status: str) -> dict[str, Any] | None:
        contact_id = self._contact_combo.currentData()
        if contact_id is None:
            self._show_banner("Please select a contact.", error=True)
            return None

        if self._lines_table.rowCount() == 0:
            self._show_banner("At least one line item is required.", error=True)
            return None

        lines = []
        for row in range(self._lines_table.rowCount()):
            desc_w = self._lines_table.cellWidget(row, _FORM_COL_DESC)
            acc_w = self._lines_table.cellWidget(row, _FORM_COL_ACCOUNT)
            qty_w = self._lines_table.cellWidget(row, _FORM_COL_QTY)
            price_w = self._lines_table.cellWidget(row, _FORM_COL_UNIT_PRICE)
            tax_w = self._lines_table.cellWidget(row, _FORM_COL_TAX_CODE)
            lines.append(
                {
                    "description": desc_w.text() if desc_w else "",
                    "account_id": acc_w.currentData() if acc_w else None,
                    "quantity": str(qty_w.value()) if qty_w else "1",
                    "unit_price": str(price_w.value()) if price_w else "0",
                    "tax_code_id": tax_w.currentData() if tax_w else None,
                }
            )

        payload: dict[str, Any] = {
            "contact_id": contact_id,
            "date": self._date_edit.date().toString("yyyy-MM-dd"),
            "lines": lines,
            "status": status,
        }
        number = self._number_edit.text().strip()
        if number:
            payload["number"] = number
        reference = self._reference_edit.text().strip()
        if reference:
            payload["reference"] = reference

        return payload

    # ------------------------------------------------------------------
    # Save actions
    # ------------------------------------------------------------------

    def _on_save_draft(self) -> None:
        payload = self._build_payload("draft")
        if payload is None:
            return
        self._do_save(payload, post_after=False)

    def _on_save_post(self) -> None:
        payload = self._build_payload("draft")
        if payload is None:
            return
        self._do_save(payload, post_after=True)

    def _do_save(self, payload: dict[str, Any], *, post_after: bool) -> None:
        try:
            if self._credit_note_id is None:
                result = create_credit_note(self._client, payload)
                saved_id = str(result.get("id", ""))
                saved_version = result.get("version")
            else:
                patch_payload = {k: v for k, v in payload.items() if k != "status"}
                etag = self._etag if self._etag is not None else 1
                status_code, result = update_credit_note(
                    self._client, self._credit_note_id, patch_payload, etag
                )
                if status_code == 409:
                    self._show_banner(
                        "Version conflict — another user has modified this credit note. "
                        "Please cancel and reload.",
                        error=True,
                    )
                    return
                saved_id = str(result.get("id", self._credit_note_id))
                saved_version = result.get("version")

            if post_after:
                etag_for_post = saved_version if saved_version is not None else 1
                post_credit_note(self._client, saved_id, etag_for_post)

        except Exception as exc:  # noqa: BLE001
            self._show_banner(f"Save failed: {exc}", error=True)
            return

        self.credit_note_saved.emit(saved_id)

    # ------------------------------------------------------------------
    # Banner helper
    # ------------------------------------------------------------------

    def _show_banner(self, message: str, *, error: bool = False) -> None:
        if error:
            style = "background: #fdecea; color: #c62828; padding: 4px;"
        else:
            style = "background: #e8f5e9; color: #2e7d32; padding: 4px;"
        self._banner.setStyleSheet(style)
        self._banner.setText(message)
        self._banner.setVisible(True)


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
