"""Invoice create/edit form.

Used for both CREATE (new blank) and EDIT (pre-filled from existing invoice).

Constructor:
    InvoiceForm(client, invoice_id=None, parent=None)

If ``invoice_id`` is provided the form loads the existing invoice data via
``GET /api/v1/invoices/{id}`` and pre-fills all fields.

Signals:
    invoice_saved(str)       — emitted with the saved invoice id after success
    cancelled()              — emitted when Cancel is clicked
    new_contact_requested()  — emitted when "New Contact" is clicked (wired later)
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.invoice_detail import get_invoice
from saebooks_desktop.services.invoice_form import (
    create_invoice,
    list_contacts_for_invoice,
    list_income_accounts,
    list_tax_codes,
    post_invoice,
    update_invoice,
)
from saebooks_desktop.views.ai_extraction_widget import DocumentExtractWidget

# Line-items table column indices
_COL_DESC = 0
_COL_ACCOUNT = 1
_COL_QTY = 2
_COL_UNIT_PRICE = 3
_COL_TAX_CODE = 4
_COL_AMOUNT = 5
_COL_REMOVE = 6

_LINE_COLUMNS = ["Description", "Account", "Qty", "Unit Price", "Tax Code", "Amount", ""]


class InvoiceForm(QWidget):
    """Create/edit form for a single invoice.

    In create mode (``invoice_id=None``) the form is blank.
    In edit mode an existing invoice is loaded and fields pre-filled.
    """

    invoice_saved = Signal(str)
    cancelled = Signal()
    new_contact_requested = Signal()

    def __init__(
        self,
        client: APIClient,
        invoice_id: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._client = client
        self._invoice_id = invoice_id
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

        # --- AI extraction section (collapsed by default) ---
        self._ai_group = QGroupBox("Extract from document")
        self._ai_group.setCheckable(True)
        self._ai_group.setChecked(False)
        ai_group_layout = QVBoxLayout(self._ai_group)
        ai_group_layout.setContentsMargins(8, 4, 8, 8)

        # Low-confidence banner (hidden until a low-confidence result arrives)
        self._ai_low_conf_banner = QLabel(
            "Low confidence \u2014 please review all fields"
        )
        self._ai_low_conf_banner.setStyleSheet(
            "background: #fff9c4; color: #5d4037; padding: 4px;"
        )
        self._ai_low_conf_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ai_low_conf_banner.setVisible(False)
        ai_group_layout.addWidget(self._ai_low_conf_banner)

        self._ai_widget = DocumentExtractWidget(client, parent=self)
        self._ai_widget.extraction_complete.connect(self._on_extraction_complete)
        ai_group_layout.addWidget(self._ai_widget)

        layout.addWidget(self._ai_group)

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
        self._new_contact_btn = QPushButton("New Contact")
        self._new_contact_btn.clicked.connect(self.new_contact_requested)
        contact_row_layout.addWidget(self._new_contact_btn)
        header_layout.addWidget(contact_row)

        # Number / Reference row
        num_ref_row = QWidget()
        num_ref_layout = QHBoxLayout(num_ref_row)
        num_ref_layout.setContentsMargins(0, 0, 0, 0)
        num_ref_layout.addWidget(QLabel("Invoice #:"))
        self._number_edit = QLineEdit()
        self._number_edit.setPlaceholderText("Auto-generated")
        num_ref_layout.addWidget(self._number_edit)
        num_ref_layout.addWidget(QLabel("Reference:"))
        self._reference_edit = QLineEdit()
        self._reference_edit.setPlaceholderText("Optional")
        num_ref_layout.addWidget(self._reference_edit)
        header_layout.addWidget(num_ref_row)

        # Dates row
        dates_row = QWidget()
        dates_layout = QHBoxLayout(dates_row)
        dates_layout.setContentsMargins(0, 0, 0, 0)
        today = QDate.currentDate()
        dates_layout.addWidget(QLabel("Issue Date:"))
        self._issue_date = QDateEdit(today)
        self._issue_date.setCalendarPopup(True)
        self._issue_date.setDisplayFormat("yyyy-MM-dd")
        dates_layout.addWidget(self._issue_date)
        dates_layout.addWidget(QLabel("Due Date:"))
        self._due_date = QDateEdit(today.addDays(30))
        self._due_date.setCalendarPopup(True)
        self._due_date.setDisplayFormat("yyyy-MM-dd")
        dates_layout.addWidget(self._due_date)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        dates_layout.addWidget(spacer)
        header_layout.addWidget(dates_row)
        layout.addWidget(header_frame)

        # --- Line items table ---
        self._lines_table = QTableWidget(0, len(_LINE_COLUMNS))
        self._lines_table.setHorizontalHeaderLabels(_LINE_COLUMNS)
        self._lines_table.horizontalHeader().setStretchLastSection(False)
        self._lines_table.horizontalHeader().setSectionResizeMode(
            _COL_DESC, self._lines_table.horizontalHeader().ResizeMode.Stretch
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

        from PySide6.QtGui import QFont
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

        # Load reference data then optionally the existing invoice
        self._load_reference_data()
        if self._invoice_id:
            self._load_existing_invoice()
        else:
            # Start with one blank line
            self._append_blank_line()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def line_count(self) -> int:
        """Return the current number of line rows."""
        return self._lines_table.rowCount()

    # ------------------------------------------------------------------
    # AI extraction
    # ------------------------------------------------------------------

    def _on_extraction_complete(self, result: dict[str, Any]) -> None:
        """Pre-fill form fields from an AI extraction result.

        Fields populated (where present in *result*):
        - contact search: matched by vendor_name against the loaded contacts
        - issue date: from ``date``
        - due date: from ``due_date``
        - reference: from ``invoice_number``
        - line items: replaced from ``line_items``

        Shows a yellow low-confidence banner when
        ``extraction_confidence < 0.70``.
        """
        confidence = result.get("extraction_confidence")
        if confidence is not None:
            try:
                if float(confidence) < 0.70:
                    self._ai_low_conf_banner.setVisible(True)
                else:
                    self._ai_low_conf_banner.setVisible(False)
            except (TypeError, ValueError):
                pass

        # Contact — fuzzy match on vendor_name
        vendor = (result.get("vendor_name") or "").strip().lower()
        if vendor:
            for i in range(self._contact_combo.count()):
                label = (self._contact_combo.itemText(i) or "").strip().lower()
                if vendor in label or label in vendor:
                    self._contact_combo.setCurrentIndex(i)
                    break

        # Reference (invoice number from the supplier's document)
        inv_num = result.get("invoice_number") or ""
        if inv_num:
            self._reference_edit.setText(str(inv_num))

        # Issue date
        date_str = result.get("date") or ""
        if date_str:
            d = QDate.fromString(str(date_str), "yyyy-MM-dd")
            if d.isValid():
                self._issue_date.setDate(d)

        # Due date
        due_str = result.get("due_date") or ""
        if due_str:
            d = QDate.fromString(str(due_str), "yyyy-MM-dd")
            if d.isValid():
                self._due_date.setDate(d)

        # Line items — replace all existing rows
        line_items = result.get("line_items") or []
        if line_items:
            while self._lines_table.rowCount() > 0:
                self._lines_table.removeRow(0)
            for item in line_items:
                row = self._lines_table.rowCount()
                self._lines_table.insertRow(row)
                self._populate_line_row(
                    row,
                    {
                        "description": item.get("description") or "",
                        "quantity": str(item.get("qty") or 1),
                        "unit_price": str(item.get("unit_price") or "0.00"),
                    },
                )
            self._recalculate_totals()

    # ------------------------------------------------------------------
    # Reference data
    # ------------------------------------------------------------------

    def _load_reference_data(self) -> None:
        """Fetch contacts, accounts, and tax codes from the API."""
        try:
            self._contacts = list_contacts_for_invoice(self._client)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._contacts = []

        try:
            self._accounts = list_income_accounts(self._client)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._accounts = []

        try:
            self._tax_codes = list_tax_codes(self._client)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._tax_codes = []

        # Populate contact combo
        self._contact_combo.clear()
        self._contact_combo.addItem("-- Select Contact --", userData=None)
        for c in self._contacts:
            self._contact_combo.addItem(c.get("name") or str(c.get("id", "")), userData=c.get("id"))

    # ------------------------------------------------------------------
    # Edit mode — load existing invoice
    # ------------------------------------------------------------------

    def _load_existing_invoice(self) -> None:
        """Fetch existing invoice and pre-fill form fields."""
        assert self._invoice_id is not None
        try:
            data = get_invoice(self._client, self._invoice_id)
        except (ServerOfflineError, Exception) as exc:  # noqa: BLE001
            self._show_banner(f"Could not load invoice: {exc}", error=True)
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

        # Dates
        if data.get("issue_date"):
            self._issue_date.setDate(QDate.fromString(str(data["issue_date"]), "yyyy-MM-dd"))
        if data.get("due_date"):
            self._due_date.setDate(QDate.fromString(str(data["due_date"]), "yyyy-MM-dd"))

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
        """Append a new blank editable row to the line items table."""
        row = self._lines_table.rowCount()
        self._lines_table.insertRow(row)
        self._populate_line_row(row, {})

    def _append_line_from_data(self, line: dict[str, Any]) -> None:
        """Append a row pre-filled from an existing line dict."""
        row = self._lines_table.rowCount()
        self._lines_table.insertRow(row)
        self._populate_line_row(row, line)

    def _populate_line_row(self, row: int, line: dict[str, Any]) -> None:
        """Wire up all cell widgets for a given row."""
        # Description
        desc_edit = QLineEdit(line.get("description") or "")
        self._lines_table.setCellWidget(row, _COL_DESC, desc_edit)

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
        self._lines_table.setCellWidget(row, _COL_ACCOUNT, account_combo)

        # Qty
        qty_spin = QDoubleSpinBox()
        qty_spin.setDecimals(2)
        qty_spin.setMinimum(0.0)
        qty_spin.setMaximum(9_999_999.99)
        qty_spin.setValue(float(line.get("quantity") or 0.0))
        qty_spin.valueChanged.connect(lambda _, r=row: self._on_line_changed(r))
        self._lines_table.setCellWidget(row, _COL_QTY, qty_spin)

        # Unit price
        price_spin = QDoubleSpinBox()
        price_spin.setDecimals(2)
        price_spin.setMinimum(0.0)
        price_spin.setMaximum(9_999_999.99)
        price_spin.setValue(float(line.get("unit_price") or 0.0))
        price_spin.valueChanged.connect(lambda _, r=row: self._on_line_changed(r))
        self._lines_table.setCellWidget(row, _COL_UNIT_PRICE, price_spin)

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
        self._lines_table.setCellWidget(row, _COL_TAX_CODE, tax_combo)

        # Amount (read-only label)
        amount_item = QTableWidgetItem("0.00")
        amount_item.setFlags(amount_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        amount_item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._lines_table.setItem(row, _COL_AMOUNT, amount_item)

        # Remove button
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(lambda _, r=row: self._on_remove_line(r))
        self._lines_table.setCellWidget(row, _COL_REMOVE, remove_btn)

        # Recalculate amount for this row
        self._update_line_amount(row)

    def _on_add_line(self) -> None:
        """Append a blank row."""
        self._append_blank_line()
        self._recalculate_totals()

    def _on_remove_line(self, row: int) -> None:
        """Remove a row, enforcing minimum 1 line."""
        if self._lines_table.rowCount() <= 1:
            return
        self._lines_table.removeRow(row)
        # Re-wire remove buttons since row indices shifted
        self._rewire_remove_buttons()
        self._recalculate_totals()

    def _rewire_remove_buttons(self) -> None:
        """Re-connect remove buttons after row index shift."""
        for r in range(self._lines_table.rowCount()):
            btn = self._lines_table.cellWidget(r, _COL_REMOVE)
            if btn is not None:
                try:
                    btn.clicked.disconnect()
                except RuntimeError:
                    pass
                btn.clicked.connect(lambda _, row=r: self._on_remove_line(row))
            # Also re-wire qty/price spinboxes
            qty_w = self._lines_table.cellWidget(r, _COL_QTY)
            price_w = self._lines_table.cellWidget(r, _COL_UNIT_PRICE)
            tax_w = self._lines_table.cellWidget(r, _COL_TAX_CODE)
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
                price_w.valueChanged.connect(lambda _, row=r: self._on_line_changed(row))
            if tax_w is not None:
                try:
                    tax_w.currentIndexChanged.disconnect()
                except RuntimeError:
                    pass
                tax_w.currentIndexChanged.connect(lambda _, row=r: self._on_line_changed(row))

    def _on_line_changed(self, row: int) -> None:
        self._update_line_amount(row)
        self._recalculate_totals()

    def _update_line_amount(self, row: int) -> None:
        """Recalculate Amount = Qty × Unit Price for a given row."""
        qty_w = self._lines_table.cellWidget(row, _COL_QTY)
        price_w = self._lines_table.cellWidget(row, _COL_UNIT_PRICE)
        if qty_w is None or price_w is None:
            return
        amount = qty_w.value() * price_w.value()
        item = self._lines_table.item(row, _COL_AMOUNT)
        if item is not None:
            item.setText(f"{amount:.2f}")

    def _recalculate_totals(self) -> None:
        """Recalculate and display Subtotal, Tax, Total from current row data."""
        subtotal = 0.0
        tax_total = 0.0

        for row in range(self._lines_table.rowCount()):
            qty_w = self._lines_table.cellWidget(row, _COL_QTY)
            price_w = self._lines_table.cellWidget(row, _COL_UNIT_PRICE)
            tax_w = self._lines_table.cellWidget(row, _COL_TAX_CODE)
            if qty_w is None or price_w is None:
                continue
            line_amount = qty_w.value() * price_w.value()
            subtotal += line_amount

            # Tax amount: look up tax code rate
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
        """Return the decimal rate (e.g. 0.1 for 10%) for a tax code id."""
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
        """Validate form and return API payload, or None if invalid."""
        contact_id = self._contact_combo.currentData()
        if contact_id is None:
            self._show_banner("Please select a contact.", error=True)
            return None

        if self._lines_table.rowCount() == 0:
            self._show_banner("At least one line item is required.", error=True)
            return None

        lines = []
        for row in range(self._lines_table.rowCount()):
            desc_w = self._lines_table.cellWidget(row, _COL_DESC)
            acc_w = self._lines_table.cellWidget(row, _COL_ACCOUNT)
            qty_w = self._lines_table.cellWidget(row, _COL_QTY)
            price_w = self._lines_table.cellWidget(row, _COL_UNIT_PRICE)
            tax_w = self._lines_table.cellWidget(row, _COL_TAX_CODE)
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
            "issue_date": self._issue_date.date().toString("yyyy-MM-dd"),
            "due_date": self._due_date.date().toString("yyyy-MM-dd"),
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
        """Perform create or update then optionally post."""
        try:
            if self._invoice_id is None:
                # Create
                result = create_invoice(self._client, payload)
                saved_id = str(result.get("id", ""))
                saved_version = result.get("version")
            else:
                # Update — remove status from PATCH payload (it's a transition-only field)
                patch_payload = {k: v for k, v in payload.items() if k != "status"}
                etag = self._etag if self._etag is not None else 1
                status_code, result = update_invoice(
                    self._client, self._invoice_id, patch_payload, etag
                )
                if status_code == 409:
                    self._show_banner(
                        "Version conflict — another user has modified this invoice. "
                        "Please cancel and reload.",
                        error=True,
                    )
                    return
                saved_id = str(result.get("id", self._invoice_id))
                saved_version = result.get("version")

            if post_after:
                etag_for_post = saved_version if saved_version is not None else 1
                post_invoice(self._client, saved_id, etag_for_post)

        except Exception as exc:  # noqa: BLE001
            self._show_banner(f"Save failed: {exc}", error=True)
            return

        self.invoice_saved.emit(saved_id)

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
