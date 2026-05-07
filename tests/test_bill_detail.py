"""Tests for BillDetailView — offscreen Qt, mocked API service layer.

All tests run without a real API server.  The service function
``saebooks_desktop.services.bill_detail.get_bill`` is patched at the
module-level import point inside the view so no HTTP calls are made.
"""
from __future__ import annotations

import os
from unittest.mock import patch

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
# Sample fixture data
# ---------------------------------------------------------------------------

_UUID_ACCOUNT = "b1b2c3d4-0000-0000-0000-000000000001"
_UUID_CONTACT = "b1b2c3d4-0000-0000-0000-000000000002"

_SAMPLE_BILL_POSTED = {
    "id": "bill-001",
    "number": "BILL-0001",
    "contact_id": _UUID_CONTACT,
    "supplier_name": "Acme Supplies",
    "issue_date": "2024-01-15",
    "due_date": "2024-02-15",
    "status": "posted",
    "subtotal": "500.00",
    "tax_total": "50.00",
    "total": "550.00",
    "lines": [
        {
            "description": "Office materials",
            "account_id": _UUID_ACCOUNT,
            "tax_code_id": None,
            "quantity": "5",
            "unit_price": "100.00",
            "line_total": "500.00",
        },
    ],
}

_SAMPLE_BILL_DRAFT = {
    "id": "bill-002",
    "number": "BILL-0002",
    "contact_id": _UUID_CONTACT,
    "supplier_name": "Beta Vendor",
    "issue_date": "2024-01-20",
    "due_date": "2024-02-20",
    "status": "draft",
    "subtotal": "200.00",
    "tax_total": "20.00",
    "total": "220.00",
    "lines": [],
}

_SAMPLE_BILL_VOIDED = {
    "id": "bill-003",
    "number": "BILL-0003",
    "contact_id": _UUID_CONTACT,
    "supplier_name": "Gamma Supplier",
    "issue_date": "2024-01-25",
    "due_date": "2024-02-25",
    "status": "voided",
    "subtotal": "300.00",
    "tax_total": "30.00",
    "total": "330.00",
    "lines": [],
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_view(qapp):
    """Create BillDetailView without calling load()."""
    from saebooks_desktop.views.bill_detail import BillDetailView

    return BillDetailView()


def _load_view(qapp, data=None, side_effect=None):
    """Create BillDetailView and call load() with mocked service."""
    from saebooks_desktop.views.bill_detail import BillDetailView

    view = BillDetailView()
    bill_id = (data or {}).get("id", "bill-test")

    if side_effect is not None:
        with patch(
            "saebooks_desktop.views.bill_detail.get_bill",
            side_effect=side_effect,
        ):
            view.load(bill_id)
    else:
        with patch(
            "saebooks_desktop.views.bill_detail.get_bill",
            return_value=data if data is not None else {},
        ):
            view.load(bill_id)

    return view


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBillDetailInstantiation:
    def test_instantiates_without_crash(self, qapp) -> None:
        view = _make_view(qapp)
        assert view is not None

    def test_has_number_label(self, qapp) -> None:
        from PySide6.QtWidgets import QLabel

        view = _make_view(qapp)
        assert isinstance(view._number_label, QLabel)

    def test_has_status_badge(self, qapp) -> None:
        from PySide6.QtWidgets import QLabel

        view = _make_view(qapp)
        assert isinstance(view._status_badge, QLabel)

    def test_has_supplier_label(self, qapp) -> None:
        from PySide6.QtWidgets import QLabel

        view = _make_view(qapp)
        assert isinstance(view._supplier_label, QLabel)

    def test_has_lines_table(self, qapp) -> None:
        from PySide6.QtWidgets import QTableView

        view = _make_view(qapp)
        assert isinstance(view._lines_table, QTableView)

    def test_lines_table_has_six_columns(self, qapp) -> None:
        view = _make_view(qapp)
        assert view._lines_model.columnCount() == 6


class TestBillDetailHeaderFields:
    def test_number_populated(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_BILL_POSTED)
        assert view._number_label.text() == "BILL-0001"

    def test_status_badge_text(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_BILL_POSTED)
        assert view._status_badge.text() == "POSTED"

    def test_supplier_name_populated(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_BILL_POSTED)
        assert view._supplier_label.text() == "Acme Supplies"

    def test_bill_date_populated(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_BILL_POSTED)
        assert view._bill_date_label.text() == "2024-01-15"

    def test_due_date_populated(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_BILL_POSTED)
        assert view._due_date_label.text() == "2024-02-15"

    def test_supplier_fallback_to_contact_id(self, qapp) -> None:
        """When supplier_name absent, falls back to contact_id string."""
        data = dict(_SAMPLE_BILL_POSTED)
        data.pop("supplier_name", None)
        view = _load_view(qapp, data=data)
        assert view._supplier_label.text() == _UUID_CONTACT


class TestBillDetailLinesTable:
    def test_lines_row_count(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_BILL_POSTED)
        assert view._lines_model.rowCount() == 1

    def test_lines_description_column(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_BILL_POSTED)
        assert view._lines_model.item(0, 0).text() == "Office materials"

    def test_lines_qty_column(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_BILL_POSTED)
        assert view._lines_model.item(0, 2).text() == "5"

    def test_lines_unit_price_column(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_BILL_POSTED)
        assert view._lines_model.item(0, 3).text() == "100.00"

    def test_lines_amount_column(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_BILL_POSTED)
        assert view._lines_model.item(0, 5).text() == "500.00"

    def test_empty_lines(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_BILL_DRAFT)
        assert view._lines_model.rowCount() == 0


class TestBillDetailTotals:
    def test_subtotal_label(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_BILL_POSTED)
        assert view._subtotal_label.text() == "500.00"

    def test_tax_label(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_BILL_POSTED)
        assert view._tax_label.text() == "50.00"

    def test_total_label(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_BILL_POSTED)
        assert view._total_label.text() == "550.00"


class TestBillDetailButtons:
    def test_edit_button_disabled(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_BILL_POSTED)
        assert not view._edit_btn.isEnabled()

    def test_void_button_disabled_for_draft(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_BILL_DRAFT)
        assert not view._void_btn.isEnabled()

    def test_void_button_disabled_for_voided(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_BILL_VOIDED)
        assert not view._void_btn.isEnabled()

    def test_void_button_enabled_for_posted(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_BILL_POSTED)
        assert view._void_btn.isEnabled()

    def test_back_button_emits_signal(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_BILL_POSTED)
        received = []
        view.back_requested.connect(lambda: received.append(True))
        view._back_btn.click()
        assert received == [True]

    def test_void_emits_signal_on_confirm(self, qapp, monkeypatch) -> None:
        from PySide6.QtWidgets import QMessageBox

        view = _load_view(qapp, data=_SAMPLE_BILL_POSTED)
        received: list[str] = []
        view.void_requested.connect(received.append)

        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *a, **kw: QMessageBox.StandardButton.Yes,
        )
        view._on_void_clicked()
        assert received == ["bill-001"]

    def test_void_does_not_emit_on_cancel(self, qapp, monkeypatch) -> None:
        from PySide6.QtWidgets import QMessageBox

        view = _load_view(qapp, data=_SAMPLE_BILL_POSTED)
        received: list[str] = []
        view.void_requested.connect(received.append)

        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *a, **kw: QMessageBox.StandardButton.No,
        )
        view._on_void_clicked()
        assert received == []


class TestBillDetailOffline:
    def test_offline_banner_shown_on_error(self, qapp) -> None:
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _load_view(qapp, side_effect=ServerOfflineError("offline"))
        assert not view._offline_label.isHidden()

    def test_offline_banner_hidden_when_data_loads(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_BILL_POSTED)
        assert view._offline_label.isHidden()
