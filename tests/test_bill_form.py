"""Tests for BillForm — offscreen Qt, mocked API service layer.

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

_UUID_SUPPLIER = "s0000000-0000-0000-0000-000000000001"
_UUID_ACCOUNT = "a0000000-0000-0000-0000-000000000001"
_UUID_TAX = "t0000000-0000-0000-0000-000000000001"

_SAMPLE_SUPPLIERS = [{"id": _UUID_SUPPLIER, "name": "Acme Supplies"}]
_SAMPLE_ACCOUNTS = [{"id": _UUID_ACCOUNT, "name": "Office Expenses"}]
_SAMPLE_TAX_CODES = [{"id": _UUID_TAX, "code": "GST10", "rate": 0.1}]

_SAMPLE_BILL = {
    "id": "bill-001",
    "number": "BILL-0001",
    "contact_id": _UUID_SUPPLIER,
    "issue_date": "2024-01-15",
    "due_date": "2024-02-15",
    "reference": "PO-456",
    "version": 1,
    "lines": [
        {
            "description": "Office supplies",
            "account_id": _UUID_ACCOUNT,
            "quantity": "2",
            "unit_price": "150.00",
            "tax_code_id": _UUID_TAX,
            "line_total": "300.00",
        }
    ],
}


# ---------------------------------------------------------------------------
# Patch targets
# ---------------------------------------------------------------------------

_PATCH_LIST_SUPPLIERS = "saebooks_desktop.views.bill_form.list_suppliers"
_PATCH_LIST_ACCOUNTS = "saebooks_desktop.views.bill_form.list_expense_accounts"
_PATCH_LIST_TAX = "saebooks_desktop.views.bill_form.list_tax_codes"
_PATCH_GET_BILL = "saebooks_desktop.views.bill_form.get_bill"
_PATCH_CREATE = "saebooks_desktop.views.bill_form.create_bill"
_PATCH_UPDATE = "saebooks_desktop.views.bill_form.update_bill"
_PATCH_POST = "saebooks_desktop.views.bill_form.post_bill"


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_client():
    return MagicMock()


def _make_form_create(qapp, suppliers=None, accounts=None, tax_codes=None):
    """Return a blank BillForm (create mode)."""
    from saebooks_desktop.views.bill_form import BillForm

    with (
        patch(_PATCH_LIST_SUPPLIERS, return_value=suppliers or _SAMPLE_SUPPLIERS),
        patch(_PATCH_LIST_ACCOUNTS, return_value=accounts or _SAMPLE_ACCOUNTS),
        patch(_PATCH_LIST_TAX, return_value=tax_codes or _SAMPLE_TAX_CODES),
    ):
        form = BillForm(_make_client())
    return form


def _make_form_edit(qapp, bill_data=None, suppliers=None, accounts=None, tax_codes=None):
    """Return a BillForm in edit mode pre-filled from bill_data."""
    from saebooks_desktop.views.bill_form import BillForm

    data = bill_data if bill_data is not None else _SAMPLE_BILL

    with (
        patch(_PATCH_LIST_SUPPLIERS, return_value=suppliers or _SAMPLE_SUPPLIERS),
        patch(_PATCH_LIST_ACCOUNTS, return_value=accounts or _SAMPLE_ACCOUNTS),
        patch(_PATCH_LIST_TAX, return_value=tax_codes or _SAMPLE_TAX_CODES),
        patch(_PATCH_GET_BILL, return_value=data),
    ):
        form = BillForm(_make_client(), bill_id=data["id"])
    return form


# ---------------------------------------------------------------------------
# Instantiation tests
# ---------------------------------------------------------------------------


class TestBillFormCreate:
    def test_instantiates_without_crash(self, qapp) -> None:
        form = _make_form_create(qapp)
        assert form is not None

    def test_supplier_combo_has_placeholder(self, qapp) -> None:
        form = _make_form_create(qapp)
        assert form._contact_combo.itemText(0) == "-- Select Supplier --"

    def test_supplier_combo_populated(self, qapp) -> None:
        form = _make_form_create(qapp)
        # Item 0 is placeholder, item 1 is Acme Supplies
        assert form._contact_combo.count() == 2
        assert form._contact_combo.itemText(1) == "Acme Supplies"

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

    def test_has_new_supplier_button(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton

        form = _make_form_create(qapp)
        assert isinstance(form._new_contact_btn, QPushButton)

    def test_new_supplier_button_label(self, qapp) -> None:
        form = _make_form_create(qapp)
        assert form._new_contact_btn.text() == "New Supplier"


# ---------------------------------------------------------------------------
# Edit mode — pre-fill
# ---------------------------------------------------------------------------


class TestBillFormEdit:
    def test_edit_mode_prefills_number(self, qapp) -> None:
        form = _make_form_edit(qapp)
        assert form._number_edit.text() == "BILL-0001"

    def test_edit_mode_prefills_reference(self, qapp) -> None:
        form = _make_form_edit(qapp)
        assert form._reference_edit.text() == "PO-456"

    def test_edit_mode_prefills_issue_date(self, qapp) -> None:
        from PySide6.QtCore import QDate

        form = _make_form_edit(qapp)
        assert form._issue_date.date() == QDate.fromString("2024-01-15", "yyyy-MM-dd")

    def test_edit_mode_prefills_due_date(self, qapp) -> None:
        from PySide6.QtCore import QDate

        form = _make_form_edit(qapp)
        assert form._due_date.date() == QDate.fromString("2024-02-15", "yyyy-MM-dd")

    def test_edit_mode_prefills_supplier(self, qapp) -> None:
        form = _make_form_edit(qapp)
        assert form._contact_combo.currentData() == _UUID_SUPPLIER

    def test_edit_mode_loads_lines(self, qapp) -> None:
        form = _make_form_edit(qapp)
        assert form.line_count() == 1

    def test_edit_mode_prefills_description(self, qapp) -> None:
        form = _make_form_edit(qapp)
        desc_w = form._lines_table.cellWidget(0, 0)
        assert desc_w is not None
        assert desc_w.text() == "Office supplies"

    def test_edit_mode_prefills_qty(self, qapp) -> None:
        form = _make_form_edit(qapp)
        qty_w = form._lines_table.cellWidget(0, 2)
        assert qty_w is not None
        assert qty_w.value() == pytest.approx(2.0)

    def test_edit_mode_prefills_unit_price(self, qapp) -> None:
        form = _make_form_edit(qapp)
        price_w = form._lines_table.cellWidget(0, 3)
        assert price_w is not None
        assert price_w.value() == pytest.approx(150.0)

    def test_edit_mode_stores_etag(self, qapp) -> None:
        form = _make_form_edit(qapp)
        assert form._etag == 1


# ---------------------------------------------------------------------------
# Line item table interactions
# ---------------------------------------------------------------------------


class TestBillFormLineItems:
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


class TestBillFormTotals:
    def test_totals_start_at_zero(self, qapp) -> None:
        form = _make_form_create(qapp)
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


class TestBillFormSaveDraft:
    def _set_supplier(self, form) -> None:
        idx = form._contact_combo.findData(_UUID_SUPPLIER)
        form._contact_combo.setCurrentIndex(idx)

    def test_save_draft_calls_create_bill(self, qapp) -> None:
        form = _make_form_create(qapp)
        self._set_supplier(form)

        mock_result = {"id": "bill-new", "version": 1}
        with patch(_PATCH_CREATE, return_value=mock_result) as mock_create:
            form._on_save_draft()

        mock_create.assert_called_once()
        args = mock_create.call_args
        payload = args[0][1]
        assert payload["status"] == "draft"
        assert payload["contact_id"] == _UUID_SUPPLIER

    def test_save_draft_emits_bill_saved(self, qapp) -> None:
        form = _make_form_create(qapp)
        self._set_supplier(form)

        received: list[str] = []
        form.bill_saved.connect(received.append)

        with patch(_PATCH_CREATE, return_value={"id": "bill-new", "version": 1}):
            form._on_save_draft()

        assert received == ["bill-new"]

    def test_save_draft_no_supplier_shows_banner(self, qapp) -> None:
        form = _make_form_create(qapp)
        form._contact_combo.setCurrentIndex(0)  # placeholder (data=None)

        received: list[str] = []
        form.bill_saved.connect(received.append)
        with patch(_PATCH_CREATE) as mock_create:
            form._on_save_draft()

        mock_create.assert_not_called()
        assert received == []
        assert not form._banner.isHidden()
        assert "supplier" in form._banner.text().lower()


# ---------------------------------------------------------------------------
# Save & Post
# ---------------------------------------------------------------------------


class TestBillFormSavePost:
    def _set_supplier(self, form) -> None:
        idx = form._contact_combo.findData(_UUID_SUPPLIER)
        form._contact_combo.setCurrentIndex(idx)

    def test_save_post_calls_create_then_post(self, qapp) -> None:
        form = _make_form_create(qapp)
        self._set_supplier(form)

        mock_result = {"id": "bill-post", "version": 2}
        with (
            patch(_PATCH_CREATE, return_value=mock_result) as mock_create,
            patch(_PATCH_POST, return_value={"id": "bill-post", "status": "posted"}) as mock_post,
        ):
            form._on_save_post()

        mock_create.assert_called_once()
        mock_post.assert_called_once()
        # post_bill(client, bill_id, etag) — second positional arg is the id
        assert mock_post.call_args[0][1] == "bill-post"

    def test_save_post_emits_bill_saved(self, qapp) -> None:
        form = _make_form_create(qapp)
        self._set_supplier(form)

        received: list[str] = []
        form.bill_saved.connect(received.append)

        with (
            patch(_PATCH_CREATE, return_value={"id": "bill-post", "version": 2}),
            patch(_PATCH_POST, return_value={}),
        ):
            form._on_save_post()

        assert received == ["bill-post"]


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


class TestBillFormCancel:
    def test_cancel_emits_cancelled_signal(self, qapp) -> None:
        form = _make_form_create(qapp)
        received = []
        form.cancelled.connect(lambda: received.append(True))
        form._cancel_btn.click()
        assert received == [True]

    def test_new_supplier_button_emits_signal(self, qapp) -> None:
        form = _make_form_create(qapp)
        received = []
        form.new_supplier_requested.connect(lambda: received.append(True))
        form._new_contact_btn.click()
        assert received == [True]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestBillFormValidation:
    def test_validation_fails_with_no_supplier(self, qapp) -> None:
        form = _make_form_create(qapp)
        form._contact_combo.setCurrentIndex(0)  # placeholder
        result = form._build_payload("draft")
        assert result is None
        assert not form._banner.isHidden()

    def test_validation_fails_with_no_lines(self, qapp) -> None:
        form = _make_form_create(qapp)
        idx = form._contact_combo.findData(_UUID_SUPPLIER)
        form._contact_combo.setCurrentIndex(idx)
        # Force-remove all rows directly (bypass the min-1 guard)
        while form._lines_table.rowCount() > 0:
            form._lines_table.removeRow(0)
        result = form._build_payload("draft")
        assert result is None
        assert not form._banner.isHidden()

    def test_validation_succeeds_with_supplier_and_line(self, qapp) -> None:
        form = _make_form_create(qapp)
        idx = form._contact_combo.findData(_UUID_SUPPLIER)
        form._contact_combo.setCurrentIndex(idx)
        result = form._build_payload("draft")
        assert result is not None
        assert result["contact_id"] == _UUID_SUPPLIER


# ---------------------------------------------------------------------------
# Etag handling on update
# ---------------------------------------------------------------------------


class TestBillFormEtag:
    def _set_supplier(self, form) -> None:
        idx = form._contact_combo.findData(_UUID_SUPPLIER)
        form._contact_combo.setCurrentIndex(idx)

    def test_update_sends_etag_in_header(self, qapp) -> None:
        form = _make_form_edit(qapp)
        self._set_supplier(form)

        mock_result = (200, {"id": "bill-001", "version": 2})
        with patch(_PATCH_UPDATE, return_value=mock_result) as mock_update:
            form._on_save_draft()

        mock_update.assert_called_once()
        # update_bill(client, bill_id, data, etag) — 4th arg is etag
        assert mock_update.call_args[0][3] == 1  # version from _SAMPLE_BILL

    def test_update_conflict_shows_banner(self, qapp) -> None:
        form = _make_form_edit(qapp)
        self._set_supplier(form)

        mock_result = (409, {"detail": "version mismatch"})
        received: list[str] = []
        form.bill_saved.connect(received.append)

        with patch(_PATCH_UPDATE, return_value=mock_result):
            form._on_save_draft()

        assert received == []
        assert not form._banner.isHidden()
        assert "conflict" in form._banner.text().lower()
