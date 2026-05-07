"""Tests for InvoiceDetailView — offscreen Qt, mocked API service layer.

All tests run without a real API server.  The service function
``saebooks_desktop.services.invoice_detail.get_invoice`` is patched at the
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

_UUID_ACCOUNT = "a1b2c3d4-0000-0000-0000-000000000001"
_UUID_TAX = "a1b2c3d4-0000-0000-0000-000000000002"
_UUID_CONTACT = "a1b2c3d4-0000-0000-0000-000000000003"

_SAMPLE_INVOICE_POSTED = {
    "id": "inv-001",
    "number": "INV-0001",
    "contact_id": _UUID_CONTACT,
    "contact_name": "Acme Corp",
    "issue_date": "2024-01-15",
    "due_date": "2024-02-15",
    "status": "posted",
    "subtotal": "1363.64",
    "tax_total": "136.36",
    "total": "1500.00",
    "lines": [
        {
            "description": "Consulting services",
            "account_id": _UUID_ACCOUNT,
            "tax_code_id": _UUID_TAX,
            "quantity": "1",
            "unit_price": "1363.64",
            "line_total": "1500.00",
        },
        {
            "description": "Travel expenses",
            "account_id": _UUID_ACCOUNT,
            "tax_code_id": None,
            "quantity": "2",
            "unit_price": "0.00",
            "line_total": "0.00",
        },
    ],
}

_SAMPLE_INVOICE_DRAFT = {
    "id": "inv-002",
    "number": "INV-0002",
    "contact_id": _UUID_CONTACT,
    "contact_name": "Beta Ltd",
    "issue_date": "2024-01-20",
    "due_date": "2024-02-20",
    "status": "draft",
    "subtotal": "250.00",
    "tax_total": "25.00",
    "total": "275.00",
    "lines": [],
}

_SAMPLE_INVOICE_VOIDED = {
    "id": "inv-003",
    "number": "INV-0003",
    "contact_id": _UUID_CONTACT,
    "contact_name": "Gamma Inc",
    "issue_date": "2024-01-25",
    "due_date": "2024-02-25",
    "status": "voided",
    "subtotal": "800.00",
    "tax_total": "80.00",
    "total": "880.00",
    "lines": [],
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_view(qapp, data=None, side_effect=None):
    """Create InvoiceDetailView without calling load()."""
    from saebooks_desktop.views.invoice_detail import InvoiceDetailView

    return InvoiceDetailView()


def _load_view(qapp, data=None, side_effect=None):
    """Create InvoiceDetailView and call load() with mocked service."""
    from saebooks_desktop.views.invoice_detail import InvoiceDetailView

    view = InvoiceDetailView()
    invoice_id = (data or {}).get("id", "inv-test")

    if side_effect is not None:
        with patch(
            "saebooks_desktop.views.invoice_detail.get_invoice",
            side_effect=side_effect,
        ):
            view.load(invoice_id)
    else:
        with patch(
            "saebooks_desktop.views.invoice_detail.get_invoice",
            return_value=data if data is not None else {},
        ):
            view.load(invoice_id)

    return view


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInvoiceDetailInstantiation:
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

    def test_has_lines_table(self, qapp) -> None:
        from PySide6.QtWidgets import QTableView

        view = _make_view(qapp)
        assert isinstance(view._lines_table, QTableView)

    def test_lines_table_has_six_columns(self, qapp) -> None:
        view = _make_view(qapp)
        assert view._lines_model.columnCount() == 6

    def test_lines_column_headers(self, qapp) -> None:
        view = _make_view(qapp)
        headers = [
            view._lines_model.horizontalHeaderItem(i).text()
            for i in range(view._lines_model.columnCount())
        ]
        assert headers == ["Description", "Account", "Qty", "Unit Price", "Tax Code", "Amount"]


class TestInvoiceDetailHeaderFields:
    def test_number_populated(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        assert view._number_label.text() == "INV-0001"

    def test_status_badge_text(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        assert view._status_badge.text() == "POSTED"

    def test_contact_name_populated(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        assert view._contact_label.text() == "Acme Corp"

    def test_issue_date_populated(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        assert view._issue_date_label.text() == "2024-01-15"

    def test_due_date_populated(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        assert view._due_date_label.text() == "2024-02-15"

    def test_contact_fallback_to_contact_id(self, qapp) -> None:
        """When contact_name absent, falls back to contact_id string."""
        data = dict(_SAMPLE_INVOICE_POSTED)
        data.pop("contact_name", None)
        view = _load_view(qapp, data=data)
        assert view._contact_label.text() == _UUID_CONTACT


class TestInvoiceDetailLinesTable:
    def test_lines_row_count(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        assert view._lines_model.rowCount() == 2

    def test_lines_description_column(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        assert view._lines_model.item(0, 0).text() == "Consulting services"

    def test_lines_qty_column(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        assert view._lines_model.item(0, 2).text() == "1"

    def test_lines_unit_price_column(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        assert view._lines_model.item(0, 3).text() == "1363.64"

    def test_lines_amount_column(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        assert view._lines_model.item(0, 5).text() == "1500.00"

    def test_empty_lines(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_INVOICE_DRAFT)
        assert view._lines_model.rowCount() == 0

    def test_amount_right_aligned(self, qapp) -> None:
        from PySide6.QtCore import Qt

        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        item = view._lines_model.item(0, 5)
        assert item.textAlignment() & Qt.AlignmentFlag.AlignRight


class TestInvoiceDetailTotals:
    def test_subtotal_label(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        assert view._subtotal_label.text() == "1363.64"

    def test_tax_label(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        assert view._tax_label.text() == "136.36"

    def test_total_label(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        assert view._total_label.text() == "1500.00"


class TestInvoiceDetailButtons:
    def test_edit_button_present(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton

        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        assert isinstance(view._edit_btn, QPushButton)

    def test_edit_button_disabled(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        assert not view._edit_btn.isEnabled()

    def test_void_button_disabled_for_draft(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_INVOICE_DRAFT)
        assert not view._void_btn.isEnabled()

    def test_void_button_disabled_for_voided(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_INVOICE_VOIDED)
        assert not view._void_btn.isEnabled()

    def test_void_button_enabled_for_posted(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        assert view._void_btn.isEnabled()

    def test_back_button_present(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton

        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        assert isinstance(view._back_btn, QPushButton)

    def test_back_button_emits_signal(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        received = []
        view.back_requested.connect(lambda: received.append(True))
        view._back_btn.click()
        assert received == [True]

    def test_void_emits_signal_on_confirm(self, qapp, monkeypatch) -> None:
        """Void button emits void_requested when user clicks Yes in dialog."""
        from PySide6.QtWidgets import QMessageBox

        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        received: list[str] = []
        view.void_requested.connect(received.append)

        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *a, **kw: QMessageBox.StandardButton.Yes,
        )
        view._on_void_clicked()
        assert received == ["inv-001"]

    def test_void_does_not_emit_on_cancel(self, qapp, monkeypatch) -> None:
        """Void button does NOT emit void_requested when user cancels."""
        from PySide6.QtWidgets import QMessageBox

        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        received: list[str] = []
        view.void_requested.connect(received.append)

        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *a, **kw: QMessageBox.StandardButton.No,
        )
        view._on_void_clicked()
        assert received == []


class TestInvoiceDetailOffline:
    def test_offline_banner_shown_on_error(self, qapp) -> None:
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _load_view(qapp, side_effect=ServerOfflineError("offline"))
        assert not view._offline_label.isHidden()

    def test_offline_banner_hidden_when_data_loads(self, qapp) -> None:
        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        assert view._offline_label.isHidden()
