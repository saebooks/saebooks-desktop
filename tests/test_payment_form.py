"""Tests for PaymentForm — offscreen Qt, mocked API service layer.

All HTTP calls are patched at the module-level import point inside the
service layer so no real server is needed.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---------------------------------------------------------------------------
# Session-scoped QApplication fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

_UUID_CUSTOMER = "c0000000-0000-0000-0000-000000000001"
_UUID_SUPPLIER = "s0000000-0000-0000-0000-000000000001"
_UUID_BANK = "b0000000-0000-0000-0000-000000000001"
_UUID_INVOICE = "inv-0000-0000-0000-000000000001"
_UUID_BILL = "bill-000-0000-0000-000000000001"

_SAMPLE_CUSTOMERS = [{"id": _UUID_CUSTOMER, "name": "Acme Corp"}]
_SAMPLE_SUPPLIERS = [{"id": _UUID_SUPPLIER, "name": "Acme Supplies"}]
_SAMPLE_BANK_ACCOUNTS = [{"id": _UUID_BANK, "name": "Main Cheque Account"}]

_SAMPLE_INVOICES = [{"id": _UUID_INVOICE, "number": "INV-0001"}]
_SAMPLE_BILLS = [{"id": _UUID_BILL, "number": "BILL-0001"}]

_SAMPLE_PAYMENT = {"id": "pay-001", "direction": "INCOMING", "amount": "500.00"}

# ---------------------------------------------------------------------------
# Patch targets
# ---------------------------------------------------------------------------

_MOD = "saebooks_desktop.views.payment_form"
_PATCH_BANK = f"{_MOD}.list_bank_accounts"
_PATCH_CUSTOMERS = f"{_MOD}.list_customers"
_PATCH_SUPPLIERS = f"{_MOD}.list_suppliers"
_PATCH_OPEN_INVOICES = f"{_MOD}.list_open_invoices"
_PATCH_OPEN_BILLS = f"{_MOD}.list_open_bills"
_PATCH_INV_BALANCE = f"{_MOD}.get_invoice_balance"
_PATCH_BILL_BALANCE = f"{_MOD}.get_bill_balance"
_PATCH_CREATE = f"{_MOD}.create_payment"


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_client():
    return MagicMock()


def _make_form_in(qapp, bank_accounts=_SAMPLE_BANK_ACCOUNTS, customers=None):
    """PaymentForm in 'in' mode (free-standing, no pre-linked invoice)."""
    from saebooks_desktop.views.payment_form import PaymentForm

    with (
        patch(_PATCH_BANK, return_value=bank_accounts),
        patch(_PATCH_CUSTOMERS, return_value=customers or _SAMPLE_CUSTOMERS),
    ):
        form = PaymentForm(_make_client(), direction="in")
    return form


def _make_form_out(qapp, bank_accounts=_SAMPLE_BANK_ACCOUNTS, suppliers=None):
    """PaymentForm in 'out' mode (free-standing, no pre-linked bill)."""
    from saebooks_desktop.views.payment_form import PaymentForm

    with (
        patch(_PATCH_BANK, return_value=bank_accounts),
        patch(_PATCH_SUPPLIERS, return_value=suppliers or _SAMPLE_SUPPLIERS),
    ):
        form = PaymentForm(_make_client(), direction="out")
    return form


def _make_form_linked_invoice(qapp, balance=500.0):
    """PaymentForm pre-linked to an invoice."""
    from saebooks_desktop.views.payment_form import PaymentForm

    with (
        patch(_PATCH_BANK, return_value=_SAMPLE_BANK_ACCOUNTS),
        patch(_PATCH_INV_BALANCE, return_value=balance),
    ):
        form = PaymentForm(_make_client(), direction="in", invoice_id=_UUID_INVOICE)
    return form


def _make_form_linked_bill(qapp, balance=300.0):
    """PaymentForm pre-linked to a bill."""
    from saebooks_desktop.views.payment_form import PaymentForm

    with (
        patch(_PATCH_BANK, return_value=_SAMPLE_BANK_ACCOUNTS),
        patch(_PATCH_BILL_BALANCE, return_value=balance),
    ):
        form = PaymentForm(_make_client(), direction="out", bill_id=_UUID_BILL)
    return form


# ---------------------------------------------------------------------------
# Mode tests
# ---------------------------------------------------------------------------


class TestPaymentFormMode:
    def test_in_mode_has_contact_combo(self, qapp) -> None:
        form = _make_form_in(qapp)
        assert form._contact_combo is not None
        assert form._contact_label is None

    def test_out_mode_has_contact_combo(self, qapp) -> None:
        form = _make_form_out(qapp)
        assert form._contact_combo is not None
        assert form._contact_label is None

    def test_in_mode_contact_combo_label_says_select_contact(self, qapp) -> None:
        form = _make_form_in(qapp)
        assert form._contact_combo is not None
        assert form._contact_combo.itemText(0) == "-- Select Contact --"

    def test_in_mode_contact_combo_has_customers(self, qapp) -> None:
        form = _make_form_in(qapp)
        assert form._contact_combo is not None
        assert form._contact_combo.count() == 2  # placeholder + Acme Corp
        assert form._contact_combo.itemText(1) == "Acme Corp"

    def test_out_mode_contact_combo_has_suppliers(self, qapp) -> None:
        form = _make_form_out(qapp)
        assert form._contact_combo is not None
        assert form._contact_combo.count() == 2  # placeholder + Acme Supplies
        assert form._contact_combo.itemText(1) == "Acme Supplies"

    def test_doc_label_says_invoice_in_in_mode(self, qapp) -> None:
        form = _make_form_in(qapp)
        assert form._doc_label_static.text() == "Invoice:"

    def test_doc_label_says_bill_in_out_mode(self, qapp) -> None:
        form = _make_form_out(qapp)
        assert form._doc_label_static.text() == "Bill:"


# ---------------------------------------------------------------------------
# Pre-linked invoice
# ---------------------------------------------------------------------------


class TestPaymentFormLinkedInvoice:
    def test_linked_invoice_shows_contact_label_not_combo(self, qapp) -> None:
        form = _make_form_linked_invoice(qapp)
        assert form._contact_label is not None
        assert form._contact_combo is None

    def test_linked_invoice_prefills_amount(self, qapp) -> None:
        form = _make_form_linked_invoice(qapp, balance=750.0)
        assert form._amount_spin.value() == pytest.approx(750.0)

    def test_linked_invoice_zero_balance_defaults_amount(self, qapp) -> None:
        form = _make_form_linked_invoice(qapp, balance=0.0)
        # Falls back to minimum (0.01)
        assert form._amount_spin.value() == pytest.approx(0.01)

    def test_linked_invoice_shows_doc_label(self, qapp) -> None:
        form = _make_form_linked_invoice(qapp)
        assert form._doc_label is not None
        assert form._doc_combo is None


# ---------------------------------------------------------------------------
# Pre-linked bill
# ---------------------------------------------------------------------------


class TestPaymentFormLinkedBill:
    def test_linked_bill_shows_contact_label_not_combo(self, qapp) -> None:
        form = _make_form_linked_bill(qapp)
        assert form._contact_label is not None
        assert form._contact_combo is None

    def test_linked_bill_prefills_amount(self, qapp) -> None:
        form = _make_form_linked_bill(qapp, balance=300.0)
        assert form._amount_spin.value() == pytest.approx(300.0)


# ---------------------------------------------------------------------------
# Bank account combo
# ---------------------------------------------------------------------------


class TestPaymentFormBankAccount:
    def test_bank_combo_populated(self, qapp) -> None:
        form = _make_form_in(qapp)
        # placeholder + Main Cheque Account
        assert form._bank_combo.count() == 2
        assert form._bank_combo.itemText(1) == "Main Cheque Account"

    def test_bank_combo_placeholder(self, qapp) -> None:
        form = _make_form_in(qapp)
        assert form._bank_combo.itemText(0) == "-- Select Bank Account --"

    def test_bank_combo_data_carries_uuid(self, qapp) -> None:
        form = _make_form_in(qapp)
        assert form._bank_combo.itemData(1) == _UUID_BANK

    def test_bank_combo_empty_when_no_accounts(self, qapp) -> None:
        form = _make_form_in(qapp, bank_accounts=[])
        # Only the placeholder
        assert form._bank_combo.count() == 1


# ---------------------------------------------------------------------------
# Payment method combo
# ---------------------------------------------------------------------------


class TestPaymentFormMethodCombo:
    def test_method_combo_has_cash(self, qapp) -> None:
        form = _make_form_in(qapp)
        texts = [form._method_combo.itemText(i) for i in range(form._method_combo.count())]
        assert "Cash" in texts

    def test_method_combo_has_eft(self, qapp) -> None:
        form = _make_form_in(qapp)
        texts = [form._method_combo.itemText(i) for i in range(form._method_combo.count())]
        assert "EFT" in texts

    def test_method_combo_has_bpay(self, qapp) -> None:
        form = _make_form_in(qapp)
        texts = [form._method_combo.itemText(i) for i in range(form._method_combo.count())]
        assert "BPAY" in texts

    def test_method_combo_has_six_options(self, qapp) -> None:
        form = _make_form_in(qapp)
        assert form._method_combo.count() == 6

    def test_method_combo_data_values(self, qapp) -> None:
        form = _make_form_in(qapp)
        values = [form._method_combo.itemData(i) for i in range(form._method_combo.count())]
        assert "cash" in values
        assert "eft" in values
        assert "bpay" in values


# ---------------------------------------------------------------------------
# Record Payment — create_payment called with correct shape
# ---------------------------------------------------------------------------


class TestPaymentFormRecordPayment:
    def _select_bank(self, form) -> None:
        idx = form._bank_combo.findData(_UUID_BANK)
        form._bank_combo.setCurrentIndex(idx)

    def _select_contact(self, form, uuid) -> None:
        if form._contact_combo is not None:
            idx = form._contact_combo.findData(uuid)
            form._contact_combo.setCurrentIndex(idx)

    def test_record_in_calls_create_payment(self, qapp) -> None:
        form = _make_form_in(qapp)
        self._select_contact(form, _UUID_CUSTOMER)
        self._select_bank(form)
        form._amount_spin.setValue(500.0)

        with patch(_PATCH_CREATE, return_value=_SAMPLE_PAYMENT) as mock_create:
            form._on_record()

        mock_create.assert_called_once()
        payload = mock_create.call_args[0][1]
        assert payload["direction"] == "INCOMING"
        assert payload["contact_id"] == _UUID_CUSTOMER
        assert payload["bank_account_id"] == _UUID_BANK
        assert float(payload["amount"]) == pytest.approx(500.0)

    def test_record_out_sends_outgoing_direction(self, qapp) -> None:
        form = _make_form_out(qapp)
        self._select_contact(form, _UUID_SUPPLIER)
        self._select_bank(form)
        form._amount_spin.setValue(250.0)

        with patch(_PATCH_CREATE, return_value={"id": "pay-out"}) as mock_create:
            form._on_record()

        payload = mock_create.call_args[0][1]
        assert payload["direction"] == "OUTGOING"

    def test_record_emits_payment_recorded(self, qapp) -> None:
        form = _make_form_in(qapp)
        self._select_contact(form, _UUID_CUSTOMER)
        self._select_bank(form)
        form._amount_spin.setValue(100.0)

        received: list[str] = []
        form.payment_recorded.connect(received.append)

        with patch(_PATCH_CREATE, return_value={"id": "pay-xyz"}):
            form._on_record()

        assert received == ["pay-xyz"]

    def test_linked_invoice_includes_allocation(self, qapp) -> None:
        form = _make_form_linked_invoice(qapp, balance=500.0)
        self._select_bank(form)

        with patch(_PATCH_CREATE, return_value=_SAMPLE_PAYMENT) as mock_create:
            form._on_record()

        payload = mock_create.call_args[0][1]
        assert len(payload["allocations"]) == 1
        assert payload["allocations"][0]["invoice_id"] == _UUID_INVOICE

    def test_linked_bill_includes_allocation(self, qapp) -> None:
        form = _make_form_linked_bill(qapp, balance=300.0)
        self._select_bank(form)

        with patch(_PATCH_CREATE, return_value={"id": "pay-bill"}) as mock_create:
            form._on_record()

        payload = mock_create.call_args[0][1]
        assert len(payload["allocations"]) == 1
        assert payload["allocations"][0]["bill_id"] == _UUID_BILL

    def test_method_included_in_payload(self, qapp) -> None:
        form = _make_form_in(qapp)
        self._select_contact(form, _UUID_CUSTOMER)
        self._select_bank(form)
        form._amount_spin.setValue(100.0)
        # Select BPAY (index 4 in the list)
        for i in range(form._method_combo.count()):
            if form._method_combo.itemData(i) == "bpay":
                form._method_combo.setCurrentIndex(i)
                break

        with patch(_PATCH_CREATE, return_value={"id": "pay-bpay"}) as mock_create:
            form._on_record()

        payload = mock_create.call_args[0][1]
        assert payload["method"] == "bpay"

    def test_reference_included_when_set(self, qapp) -> None:
        form = _make_form_in(qapp)
        self._select_contact(form, _UUID_CUSTOMER)
        self._select_bank(form)
        form._amount_spin.setValue(100.0)
        form._reference_edit.setText("REF-001")

        with patch(_PATCH_CREATE, return_value={"id": "pay-ref"}) as mock_create:
            form._on_record()

        payload = mock_create.call_args[0][1]
        assert payload.get("reference") == "REF-001"


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


class TestPaymentFormCancel:
    def test_cancel_emits_cancelled(self, qapp) -> None:
        form = _make_form_in(qapp)
        received = []
        form.cancelled.connect(lambda: received.append(True))
        form._cancel_btn.click()
        assert received == [True]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestPaymentFormValidation:
    def test_validation_fails_no_contact(self, qapp) -> None:
        form = _make_form_in(qapp)
        # Contact at placeholder (index 0, data=None)
        form._contact_combo.setCurrentIndex(0)
        result = form._build_payload()
        assert result is None
        assert not form._banner.isHidden()
        assert "contact" in form._banner.text().lower()

    def test_validation_fails_no_bank_account(self, qapp) -> None:
        form = _make_form_in(qapp)
        # Select a contact
        idx = form._contact_combo.findData(_UUID_CUSTOMER)
        form._contact_combo.setCurrentIndex(idx)
        # Bank stays at placeholder (index 0, data=None)
        form._bank_combo.setCurrentIndex(0)
        form._amount_spin.setValue(100.0)
        result = form._build_payload()
        assert result is None
        assert not form._banner.isHidden()
        assert "bank" in form._banner.text().lower()

    def test_validation_succeeds_with_contact_and_bank(self, qapp) -> None:
        form = _make_form_in(qapp)
        idx_c = form._contact_combo.findData(_UUID_CUSTOMER)
        form._contact_combo.setCurrentIndex(idx_c)
        idx_b = form._bank_combo.findData(_UUID_BANK)
        form._bank_combo.setCurrentIndex(idx_b)
        form._amount_spin.setValue(100.0)
        result = form._build_payload()
        assert result is not None
        assert result["direction"] == "INCOMING"
