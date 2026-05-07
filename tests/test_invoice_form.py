"""Tests for InvoiceForm — offscreen Qt, mocked API service layer.

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

_UUID_CONTACT = "c0000000-0000-0000-0000-000000000001"
_UUID_ACCOUNT = "a0000000-0000-0000-0000-000000000001"
_UUID_TAX = "t0000000-0000-0000-0000-000000000001"

_SAMPLE_CONTACTS = [{"id": _UUID_CONTACT, "name": "Acme Corp"}]
_SAMPLE_ACCOUNTS = [{"id": _UUID_ACCOUNT, "name": "Sales Revenue"}]
_SAMPLE_TAX_CODES = [{"id": _UUID_TAX, "code": "GST10", "rate": 0.1}]

_SAMPLE_INVOICE = {
    "id": "inv-001",
    "number": "INV-0001",
    "contact_id": _UUID_CONTACT,
    "issue_date": "2024-01-15",
    "due_date": "2024-02-15",
    "reference": "PO-123",
    "version": 1,
    "lines": [
        {
            "description": "Consulting",
            "account_id": _UUID_ACCOUNT,
            "quantity": "2",
            "unit_price": "500.00",
            "tax_code_id": _UUID_TAX,
            "line_total": "1000.00",
        }
    ],
}


# ---------------------------------------------------------------------------
# Patch targets
# ---------------------------------------------------------------------------

_PATCH_LIST_CONTACTS = "saebooks_desktop.views.invoice_form.list_contacts_for_invoice"
_PATCH_LIST_ACCOUNTS = "saebooks_desktop.views.invoice_form.list_income_accounts"
_PATCH_LIST_TAX = "saebooks_desktop.views.invoice_form.list_tax_codes"
_PATCH_GET_INVOICE = "saebooks_desktop.views.invoice_form.get_invoice"
_PATCH_CREATE = "saebooks_desktop.views.invoice_form.create_invoice"
_PATCH_UPDATE = "saebooks_desktop.views.invoice_form.update_invoice"
_PATCH_POST = "saebooks_desktop.views.invoice_form.post_invoice"


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_client():
    return MagicMock()


def _make_form_create(qapp, contacts=None, accounts=None, tax_codes=None):
    """Return a blank InvoiceForm (create mode)."""
    from saebooks_desktop.views.invoice_form import InvoiceForm

    with (
        patch(_PATCH_LIST_CONTACTS, return_value=contacts or _SAMPLE_CONTACTS),
        patch(_PATCH_LIST_ACCOUNTS, return_value=accounts or _SAMPLE_ACCOUNTS),
        patch(_PATCH_LIST_TAX, return_value=tax_codes or _SAMPLE_TAX_CODES),
    ):
        form = InvoiceForm(_make_client())
    return form


def _make_form_edit(qapp, invoice_data=None, contacts=None, accounts=None, tax_codes=None):
    """Return an InvoiceForm in edit mode pre-filled from invoice_data."""
    from saebooks_desktop.views.invoice_form import InvoiceForm

    data = invoice_data if invoice_data is not None else _SAMPLE_INVOICE

    with (
        patch(_PATCH_LIST_CONTACTS, return_value=contacts or _SAMPLE_CONTACTS),
        patch(_PATCH_LIST_ACCOUNTS, return_value=accounts or _SAMPLE_ACCOUNTS),
        patch(_PATCH_LIST_TAX, return_value=tax_codes or _SAMPLE_TAX_CODES),
        patch(_PATCH_GET_INVOICE, return_value=data),
    ):
        form = InvoiceForm(_make_client(), invoice_id=data["id"])
    return form


# ---------------------------------------------------------------------------
# Instantiation tests
# ---------------------------------------------------------------------------


class TestInvoiceFormCreate:
    def test_instantiates_without_crash(self, qapp) -> None:
        form = _make_form_create(qapp)
        assert form is not None

    def test_contact_combo_has_placeholder(self, qapp) -> None:
        form = _make_form_create(qapp)
        assert form._contact_combo.itemText(0) == "-- Select Contact --"

    def test_contact_combo_populated(self, qapp) -> None:
        form = _make_form_create(qapp)
        # Item 0 is placeholder, item 1 is Acme Corp
        assert form._contact_combo.count() == 2
        assert form._contact_combo.itemText(1) == "Acme Corp"

    def test_number_edit_is_empty(self, qapp) -> None:
        form = _make_form_create(qapp)
        assert form._number_edit.text() == ""

    def test_issue_date_defaults_to_today(self, qapp) -> None:
        from PySide6.QtCore import QDate

        form = _make_form_create(qapp)
        assert form._issue_date.date() == QDate.currentDate()

    def test_due_date_defaults_to_today_plus_30(self, qapp) -> None:
        from PySide6.QtCore import QDate

        form = _make_form_create(qapp)
        assert form._due_date.date() == QDate.currentDate().addDays(30)

    def test_starts_with_one_line(self, qapp) -> None:
        form = _make_form_create(qapp)
        assert form.line_count() == 1

    def test_has_save_draft_button(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton

        form = _make_form_create(qapp)
        assert isinstance(form._save_draft_btn, QPushButton)

    def test_has_save_post_button(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton

        form = _make_form_create(qapp)
        assert isinstance(form._save_post_btn, QPushButton)

    def test_has_cancel_button(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton

        form = _make_form_create(qapp)
        assert isinstance(form._cancel_btn, QPushButton)

    def test_has_new_contact_button(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton

        form = _make_form_create(qapp)
        assert isinstance(form._new_contact_btn, QPushButton)


# ---------------------------------------------------------------------------
# Edit mode — pre-fill
# ---------------------------------------------------------------------------


class TestInvoiceFormEdit:
    def test_edit_mode_prefills_number(self, qapp) -> None:
        form = _make_form_edit(qapp)
        assert form._number_edit.text() == "INV-0001"

    def test_edit_mode_prefills_reference(self, qapp) -> None:
        form = _make_form_edit(qapp)
        assert form._reference_edit.text() == "PO-123"

    def test_edit_mode_prefills_issue_date(self, qapp) -> None:
        from PySide6.QtCore import QDate

        form = _make_form_edit(qapp)
        assert form._issue_date.date() == QDate.fromString("2024-01-15", "yyyy-MM-dd")

    def test_edit_mode_prefills_due_date(self, qapp) -> None:
        from PySide6.QtCore import QDate

        form = _make_form_edit(qapp)
        assert form._due_date.date() == QDate.fromString("2024-02-15", "yyyy-MM-dd")

    def test_edit_mode_prefills_contact(self, qapp) -> None:
        form = _make_form_edit(qapp)
        assert form._contact_combo.currentData() == _UUID_CONTACT

    def test_edit_mode_loads_lines(self, qapp) -> None:
        form = _make_form_edit(qapp)
        assert form.line_count() == 1

    def test_edit_mode_prefills_description(self, qapp) -> None:
        form = _make_form_edit(qapp)
        desc_w = form._lines_table.cellWidget(0, 0)
        assert desc_w is not None
        assert desc_w.text() == "Consulting"

    def test_edit_mode_prefills_qty(self, qapp) -> None:
        form = _make_form_edit(qapp)
        qty_w = form._lines_table.cellWidget(0, 2)
        assert qty_w is not None
        assert qty_w.value() == pytest.approx(2.0)

    def test_edit_mode_prefills_unit_price(self, qapp) -> None:
        form = _make_form_edit(qapp)
        price_w = form._lines_table.cellWidget(0, 3)
        assert price_w is not None
        assert price_w.value() == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# Line item table interactions
# ---------------------------------------------------------------------------


class TestInvoiceFormLineItems:
    def test_add_line_appends_row(self, qapp) -> None:
        form = _make_form_create(qapp)
        assert form.line_count() == 1
        form._on_add_line()
        assert form.line_count() == 2

    def test_add_line_three_times(self, qapp) -> None:
        form = _make_form_create(qapp)
        form._on_add_line()
        form._on_add_line()
        form._on_add_line()
        assert form.line_count() == 4

    def test_remove_line_removes_row(self, qapp) -> None:
        form = _make_form_create(qapp)
        form._on_add_line()
        assert form.line_count() == 2
        form._on_remove_line(0)
        assert form.line_count() == 1

    def test_remove_line_enforces_minimum_one(self, qapp) -> None:
        """Cannot remove below 1 line."""
        form = _make_form_create(qapp)
        assert form.line_count() == 1
        form._on_remove_line(0)
        assert form.line_count() == 1

    def test_amount_updates_on_qty_change(self, qapp) -> None:
        form = _make_form_create(qapp)
        qty_w = form._lines_table.cellWidget(0, 2)
        price_w = form._lines_table.cellWidget(0, 3)
        qty_w.setValue(3.0)
        price_w.setValue(100.0)
        form._update_line_amount(0)
        item = form._lines_table.item(0, 5)
        assert item is not None
        assert item.text() == "300.00"

    def test_amount_updates_on_price_change(self, qapp) -> None:
        form = _make_form_create(qapp)
        qty_w = form._lines_table.cellWidget(0, 2)
        price_w = form._lines_table.cellWidget(0, 3)
        qty_w.setValue(1.0)
        price_w.setValue(250.0)
        form._update_line_amount(0)
        item = form._lines_table.item(0, 5)
        assert item.text() == "250.00"

    def test_amount_column_is_readonly(self, qapp) -> None:
        from PySide6.QtCore import Qt

        form = _make_form_create(qapp)
        item = form._lines_table.item(0, 5)
        assert item is not None
        assert not (item.flags() & Qt.ItemFlag.ItemIsEditable)


# ---------------------------------------------------------------------------
# Totals recalculation
# ---------------------------------------------------------------------------


class TestInvoiceFormTotals:
    def test_totals_start_at_zero(self, qapp) -> None:
        form = _make_form_create(qapp)
        # No qty/price set yet — all zero
        assert form._subtotal_label.text() == "0.00"
        assert form._tax_label.text() == "0.00"
        assert form._total_label.text() == "0.00"

    def test_subtotal_correct(self, qapp) -> None:
        form = _make_form_create(qapp)
        qty_w = form._lines_table.cellWidget(0, 2)
        price_w = form._lines_table.cellWidget(0, 3)
        qty_w.setValue(2.0)
        price_w.setValue(500.0)
        form._recalculate_totals()
        assert form._subtotal_label.text() == "1000.00"

    def test_tax_calculated_from_rate(self, qapp) -> None:
        """GST10 has rate=0.1, so tax on 1000 = 100."""
        form = _make_form_create(qapp)
        qty_w = form._lines_table.cellWidget(0, 2)
        price_w = form._lines_table.cellWidget(0, 3)
        tax_w = form._lines_table.cellWidget(0, 4)
        qty_w.setValue(2.0)
        price_w.setValue(500.0)
        # Select GST10
        idx = tax_w.findData(_UUID_TAX)
        tax_w.setCurrentIndex(idx)
        form._recalculate_totals()
        assert form._tax_label.text() == "100.00"
        assert form._total_label.text() == "1100.00"

    def test_total_equals_subtotal_plus_tax(self, qapp) -> None:
        form = _make_form_create(qapp)
        qty_w = form._lines_table.cellWidget(0, 2)
        price_w = form._lines_table.cellWidget(0, 3)
        tax_w = form._lines_table.cellWidget(0, 4)
        qty_w.setValue(1.0)
        price_w.setValue(200.0)
        idx = tax_w.findData(_UUID_TAX)
        tax_w.setCurrentIndex(idx)
        form._recalculate_totals()
        subtotal = float(form._subtotal_label.text())
        tax = float(form._tax_label.text())
        total = float(form._total_label.text())
        assert total == pytest.approx(subtotal + tax)


# ---------------------------------------------------------------------------
# Save as Draft
# ---------------------------------------------------------------------------


class TestInvoiceFormSaveDraft:
    def _set_contact(self, form) -> None:
        idx = form._contact_combo.findData(_UUID_CONTACT)
        form._contact_combo.setCurrentIndex(idx)

    def test_save_draft_calls_create_invoice(self, qapp) -> None:
        form = _make_form_create(qapp)
        self._set_contact(form)

        mock_result = {"id": "inv-new", "version": 1}
        with patch(_PATCH_CREATE, return_value=mock_result) as mock_create:
            form._on_save_draft()

        mock_create.assert_called_once()
        args = mock_create.call_args
        payload = args[0][1]
        assert payload["status"] == "draft"
        assert payload["contact_id"] == _UUID_CONTACT

    def test_save_draft_emits_invoice_saved(self, qapp) -> None:
        form = _make_form_create(qapp)
        self._set_contact(form)

        received: list[str] = []
        form.invoice_saved.connect(received.append)

        with patch(_PATCH_CREATE, return_value={"id": "inv-new", "version": 1}):
            form._on_save_draft()

        assert received == ["inv-new"]

    def test_save_draft_no_contact_shows_banner(self, qapp) -> None:
        form = _make_form_create(qapp)
        # Do NOT select a contact — index 0 is placeholder (data=None)
        form._contact_combo.setCurrentIndex(0)

        received: list[str] = []
        form.invoice_saved.connect(received.append)
        with patch(_PATCH_CREATE) as mock_create:
            form._on_save_draft()

        mock_create.assert_not_called()
        assert received == []
        # Banner is shown — check it has been given text and is not hidden
        assert not form._banner.isHidden()
        assert "contact" in form._banner.text().lower()


# ---------------------------------------------------------------------------
# Save & Post
# ---------------------------------------------------------------------------


class TestInvoiceFormSavePost:
    def _set_contact(self, form) -> None:
        idx = form._contact_combo.findData(_UUID_CONTACT)
        form._contact_combo.setCurrentIndex(idx)

    def test_save_post_calls_create_then_post(self, qapp) -> None:
        form = _make_form_create(qapp)
        self._set_contact(form)

        mock_result = {"id": "inv-post", "version": 2}
        with (
            patch(_PATCH_CREATE, return_value=mock_result) as mock_create,
            patch(_PATCH_POST, return_value={"id": "inv-post", "status": "posted"}) as mock_post,
        ):
            form._on_save_post()

        mock_create.assert_called_once()
        mock_post.assert_called_once()
        # First arg to post_invoice is client, second is id, third is etag
        assert mock_post.call_args[0][1] == "inv-post"

    def test_save_post_emits_invoice_saved(self, qapp) -> None:
        form = _make_form_create(qapp)
        self._set_contact(form)

        received: list[str] = []
        form.invoice_saved.connect(received.append)

        with (
            patch(_PATCH_CREATE, return_value={"id": "inv-post", "version": 2}),
            patch(_PATCH_POST, return_value={}),
        ):
            form._on_save_post()

        assert received == ["inv-post"]


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


class TestInvoiceFormCancel:
    def test_cancel_emits_cancelled_signal(self, qapp) -> None:
        form = _make_form_create(qapp)
        received = []
        form.cancelled.connect(lambda: received.append(True))
        form._cancel_btn.click()
        assert received == [True]

    def test_new_contact_button_emits_signal(self, qapp) -> None:
        form = _make_form_create(qapp)
        received = []
        form.new_contact_requested.connect(lambda: received.append(True))
        form._new_contact_btn.click()
        assert received == [True]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestInvoiceFormValidation:
    def test_validation_fails_with_no_contact(self, qapp) -> None:
        form = _make_form_create(qapp)
        form._contact_combo.setCurrentIndex(0)  # placeholder
        result = form._build_payload("draft")
        assert result is None
        assert not form._banner.isHidden()

    def test_validation_fails_with_no_lines(self, qapp) -> None:
        form = _make_form_create(qapp)
        idx = form._contact_combo.findData(_UUID_CONTACT)
        form._contact_combo.setCurrentIndex(idx)
        # Force-remove all rows directly (bypass the min-1 guard)
        while form._lines_table.rowCount() > 0:
            form._lines_table.removeRow(0)
        result = form._build_payload("draft")
        assert result is None
        assert not form._banner.isHidden()

    def test_validation_succeeds_with_contact_and_line(self, qapp) -> None:
        form = _make_form_create(qapp)
        idx = form._contact_combo.findData(_UUID_CONTACT)
        form._contact_combo.setCurrentIndex(idx)
        result = form._build_payload("draft")
        assert result is not None
        assert result["contact_id"] == _UUID_CONTACT
