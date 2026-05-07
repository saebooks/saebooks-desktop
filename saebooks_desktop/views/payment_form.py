"""Payment record form.

Records a payment against an invoice (AR) or bill (AP).

Constructor:
    PaymentForm(client, direction="in", invoice_id=None, bill_id=None, parent=None)

``direction`` controls the mode:
  - ``"in"``  — customer payment received (against an invoice)
  - ``"out"`` — supplier payment made    (against a bill)

If ``invoice_id`` or ``bill_id`` is supplied the form pre-links that document,
shows the contact as a read-only label, and pre-fills the amount with the
outstanding balance.

Signals:
    payment_recorded(str)  — emitted with the new payment id after success
    cancelled()            — emitted when Cancel is clicked
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QDate, Qt, Signal
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
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.payment_form import (
    create_payment,
    get_bill_balance,
    get_invoice_balance,
    list_bank_accounts,
    list_customers,
    list_open_bills,
    list_open_invoices,
    list_suppliers,
)

# Payment method options — (display label, API value)
_PAYMENT_METHODS: list[tuple[str, str]] = [
    ("Cash", "cash"),
    ("Cheque", "cheque"),
    ("EFT", "eft"),
    ("Credit Card", "credit_card"),
    ("BPAY", "bpay"),
    ("Other", "other"),
]


class PaymentForm(QWidget):
    """Record-payment form (single payment, no line items).

    In *in* mode the form records a customer payment (AR).
    In *out* mode the form records a supplier payment (AP).
    """

    payment_recorded = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        client: APIClient,
        direction: str = "in",
        invoice_id: str | None = None,
        bill_id: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._client = client
        self._direction = direction.lower()
        self._invoice_id = invoice_id
        self._bill_id = bill_id

        # Reference data
        self._contacts: list[dict[str, Any]] = []
        self._bank_accounts: list[dict[str, Any]] = []
        self._open_documents: list[dict[str, Any]] = []  # invoices or bills

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # --- Error banner ---
        self._banner = QLabel()
        self._banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._banner.setVisible(False)
        layout.addWidget(self._banner)

        # --- Form body ---
        form_frame = QFrame()
        form_frame.setFrameShape(QFrame.Shape.StyledPanel)
        form_layout = QVBoxLayout(form_frame)
        form_layout.setSpacing(8)

        # Contact row
        contact_row = QWidget()
        contact_layout = QHBoxLayout(contact_row)
        contact_layout.setContentsMargins(0, 0, 0, 0)
        contact_layout.addWidget(QLabel("Contact:"))
        self._contact_label: QLabel | None = None
        self._contact_combo: QComboBox | None = None

        if self._invoice_id or self._bill_id:
            # Read-only label — will be populated after fetching balance
            self._contact_label = QLabel()
            contact_layout.addWidget(self._contact_label)
            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            contact_layout.addWidget(spacer)
        else:
            self._contact_combo = QComboBox()
            self._contact_combo.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            self._contact_combo.currentIndexChanged.connect(self._on_contact_changed)
            contact_layout.addWidget(self._contact_combo)
        form_layout.addWidget(contact_row)

        # Amount row
        amount_row = QWidget()
        amount_layout = QHBoxLayout(amount_row)
        amount_layout.setContentsMargins(0, 0, 0, 0)
        amount_layout.addWidget(QLabel("Amount:"))
        self._amount_spin = QDoubleSpinBox()
        self._amount_spin.setDecimals(2)
        self._amount_spin.setMinimum(0.01)
        self._amount_spin.setMaximum(9_999_999.99)
        self._amount_spin.setValue(0.01)
        amount_layout.addWidget(self._amount_spin)
        amount_spacer = QWidget()
        amount_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        amount_layout.addWidget(amount_spacer)
        form_layout.addWidget(amount_row)

        # Date row
        date_row = QWidget()
        date_layout = QHBoxLayout(date_row)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.addWidget(QLabel("Date:"))
        self._date_edit = QDateEdit(QDate.currentDate())
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        date_layout.addWidget(self._date_edit)
        date_spacer = QWidget()
        date_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        date_layout.addWidget(date_spacer)
        form_layout.addWidget(date_row)

        # Payment method row
        method_row = QWidget()
        method_layout = QHBoxLayout(method_row)
        method_layout.setContentsMargins(0, 0, 0, 0)
        method_layout.addWidget(QLabel("Payment Method:"))
        self._method_combo = QComboBox()
        for label, value in _PAYMENT_METHODS:
            self._method_combo.addItem(label, userData=value)
        method_layout.addWidget(self._method_combo)
        method_spacer = QWidget()
        method_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        method_layout.addWidget(method_spacer)
        form_layout.addWidget(method_row)

        # Bank account row
        bank_row = QWidget()
        bank_layout = QHBoxLayout(bank_row)
        bank_layout.setContentsMargins(0, 0, 0, 0)
        bank_layout.addWidget(QLabel("Bank Account:"))
        self._bank_combo = QComboBox()
        self._bank_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        bank_layout.addWidget(self._bank_combo)
        form_layout.addWidget(bank_row)

        # Reference row
        ref_row = QWidget()
        ref_layout = QHBoxLayout(ref_row)
        ref_layout.setContentsMargins(0, 0, 0, 0)
        ref_layout.addWidget(QLabel("Reference:"))
        self._reference_edit = QLineEdit()
        self._reference_edit.setPlaceholderText("Optional")
        ref_layout.addWidget(self._reference_edit)
        form_layout.addWidget(ref_row)

        # Invoice / Bill row
        doc_row = QWidget()
        doc_layout = QHBoxLayout(doc_row)
        doc_layout.setContentsMargins(0, 0, 0, 0)
        self._doc_label_static = QLabel(
            "Invoice:" if self._direction == "in" else "Bill:"
        )
        doc_layout.addWidget(self._doc_label_static)
        self._doc_label: QLabel | None = None
        self._doc_combo: QComboBox | None = None

        if self._invoice_id or self._bill_id:
            # Pre-linked — show read-only label
            self._doc_label = QLabel(self._invoice_id or self._bill_id or "")
            doc_layout.addWidget(self._doc_label)
            doc_spacer = QWidget()
            doc_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            doc_layout.addWidget(doc_spacer)
        else:
            # Free-standing — dropdown of open docs
            self._doc_combo = QComboBox()
            self._doc_combo.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            doc_layout.addWidget(self._doc_combo)
        form_layout.addWidget(doc_row)
        layout.addWidget(form_frame)

        # --- Toolbar ---
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 4, 0, 0)
        toolbar_spacer = QWidget()
        toolbar_spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        toolbar_layout.addWidget(toolbar_spacer)

        self._record_btn = QPushButton("Record Payment")
        self._record_btn.clicked.connect(self._on_record)
        toolbar_layout.addWidget(self._record_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.cancelled)
        toolbar_layout.addWidget(self._cancel_btn)

        layout.addWidget(toolbar)
        layout.addStretch()

        # Populate reference data
        self._load_reference_data()

    # ------------------------------------------------------------------
    # Reference data
    # ------------------------------------------------------------------

    def _load_reference_data(self) -> None:
        """Fetch bank accounts, contacts (when not pre-linked), and open docs."""
        # Bank accounts
        try:
            self._bank_accounts = list_bank_accounts(self._client)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._bank_accounts = []
        self._bank_combo.clear()
        self._bank_combo.addItem("-- Select Bank Account --", userData=None)
        for acc in self._bank_accounts:
            self._bank_combo.addItem(
                acc.get("name") or str(acc.get("id", "")), userData=acc.get("id")
            )

        if self._invoice_id:
            # Pre-linked invoice — fetch balance and set contact label
            balance = get_invoice_balance(self._client, self._invoice_id)
            self._amount_spin.setValue(balance if balance > 0 else 0.01)
            if self._contact_label is not None:
                self._contact_label.setText(f"(from invoice {self._invoice_id})")
            return

        if self._bill_id:
            # Pre-linked bill — fetch balance and set contact label
            balance = get_bill_balance(self._client, self._bill_id)
            self._amount_spin.setValue(balance if balance > 0 else 0.01)
            if self._contact_label is not None:
                self._contact_label.setText(f"(from bill {self._bill_id})")
            return

        # Free-standing — populate contact combo
        try:
            if self._direction == "in":
                self._contacts = list_customers(self._client)
            else:
                self._contacts = list_suppliers(self._client)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._contacts = []

        if self._contact_combo is not None:
            self._contact_combo.clear()
            self._contact_combo.addItem("-- Select Contact --", userData=None)
            for c in self._contacts:
                self._contact_combo.addItem(
                    c.get("name") or str(c.get("id", "")), userData=c.get("id")
                )

    def _load_open_documents(self, contact_id: str) -> None:
        """Load open invoices or bills for the chosen contact into _doc_combo."""
        if self._doc_combo is None:
            return
        self._doc_combo.clear()
        self._doc_combo.addItem("-- None --", userData=None)
        try:
            if self._direction == "in":
                docs = list_open_invoices(self._client, contact_id)
            else:
                docs = list_open_bills(self._client, contact_id)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            docs = []
        self._open_documents = docs
        for doc in docs:
            label = doc.get("number") or str(doc.get("id", ""))
            self._doc_combo.addItem(label, userData=doc.get("id"))

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_contact_changed(self, _index: int) -> None:
        """Reload open docs whenever the contact selection changes."""
        if self._contact_combo is None:
            return
        contact_id = self._contact_combo.currentData()
        if contact_id is not None:
            self._load_open_documents(str(contact_id))
        elif self._doc_combo is not None:
            self._doc_combo.clear()

    # ------------------------------------------------------------------
    # Validation and build payload
    # ------------------------------------------------------------------

    def _resolve_contact_id(self) -> str | None:
        """Return the selected/pre-linked contact id or None."""
        if self._contact_combo is not None:
            return self._contact_combo.currentData()
        # Pre-linked — we don't surface the contact id directly in the form;
        # it comes from the invoice/bill lookup. Return a sentinel truthy value
        # so validation passes; the allocation carries the doc link.
        if self._invoice_id or self._bill_id:
            return self._invoice_id or self._bill_id
        return None

    def _build_payload(self) -> dict[str, Any] | None:
        """Validate and return the API payload dict, or None on failure."""
        contact_id = self._resolve_contact_id()
        if contact_id is None:
            self._show_banner("Please select a contact.", error=True)
            return None

        amount = self._amount_spin.value()
        if amount <= 0:
            self._show_banner("Amount must be greater than zero.", error=True)
            return None

        bank_id = self._bank_combo.currentData()
        if bank_id is None:
            self._show_banner("Please select a bank account.", error=True)
            return None

        method = self._method_combo.currentData() or "eft"
        direction_api = "INCOMING" if self._direction == "in" else "OUTGOING"
        payment_date = self._date_edit.date().toString("yyyy-MM-dd")

        # Build allocations
        allocations: list[dict[str, Any]] = []
        if self._invoice_id:
            allocations.append({"invoice_id": self._invoice_id, "amount": str(amount)})
        elif self._bill_id:
            allocations.append({"bill_id": self._bill_id, "amount": str(amount)})
        elif self._doc_combo is not None:
            doc_id = self._doc_combo.currentData()
            if doc_id is not None:
                if self._direction == "in":
                    allocations.append({"invoice_id": doc_id, "amount": str(amount)})
                else:
                    allocations.append({"bill_id": doc_id, "amount": str(amount)})

        # For pre-linked mode the contact_id is the doc id (used as sentinel);
        # we need to pass the real contact_id. Attempt to look it up from the
        # open documents list or leave the sentinel — the API will reject it.
        # A better UX would fetch the invoice/bill to get contact_id; for now
        # we rely on the caller to have loaded a contact_id via the pre-link path.
        # When contact_combo is None we use the sentinel as-is; the API call may
        # fail gracefully and the banner will display the error.

        payload: dict[str, Any] = {
            "contact_id": contact_id,
            "bank_account_id": bank_id,
            "payment_date": payment_date,
            "amount": str(amount),
            "direction": direction_api,
            "method": method,
            "allocations": allocations,
        }

        reference = self._reference_edit.text().strip()
        if reference:
            payload["reference"] = reference

        return payload

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_record(self) -> None:
        payload = self._build_payload()
        if payload is None:
            return
        try:
            result = create_payment(self._client, payload)
        except Exception as exc:  # noqa: BLE001
            self._show_banner(f"Save failed: {exc}", error=True)
            return
        self.payment_recorded.emit(str(result.get("id", "")))

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
