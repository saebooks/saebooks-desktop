"""Tests for AI document extraction — service, widget, and form pre-fill.

All HTTP calls are mocked; no real server or filesystem access needed beyond
a tmp_path fixture for the service-level tests.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# ---------------------------------------------------------------------------
# Session-scoped QApplication
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# Shared sample data
# ---------------------------------------------------------------------------

_UUID_SUPPLIER = "s0000000-0000-0000-0000-000000000001"
_UUID_CONTACT = "c0000000-0000-0000-0000-000000000001"
_UUID_ACCOUNT = "a0000000-0000-0000-0000-000000000001"
_UUID_TAX = "t0000000-0000-0000-0000-000000000001"

_SAMPLE_SUPPLIERS = [{"id": _UUID_SUPPLIER, "name": "Acme Supplies"}]
_SAMPLE_CONTACTS = [{"id": _UUID_CONTACT, "name": "Acme Corp"}]
_SAMPLE_ACCOUNTS = [{"id": _UUID_ACCOUNT, "name": "Office Expenses"}]
_SAMPLE_TAX_CODES = [{"id": _UUID_TAX, "code": "GST10", "rate": 0.1}]

_HIGH_CONF_RESULT = {
    "vendor_name": "Acme Supplies",
    "invoice_number": "INV-9999",
    "date": "2026-04-25",
    "due_date": "2026-05-25",
    "subtotal": "100.00",
    "tax_amount": "10.00",
    "total": "110.00",
    "currency": "AUD",
    "notes": "",
    "extraction_confidence": 0.92,
    "line_items": [
        {
            "description": "Office supplies",
            "qty": 2,
            "unit_price": "50.00",
            "amount": "100.00",
            "tax_code": None,
        }
    ],
}

_LOW_CONF_RESULT = {
    **_HIGH_CONF_RESULT,
    "extraction_confidence": 0.55,
}

# Patch targets
_PATCH_BILL_SUPPLIERS = "saebooks_desktop.views.bill_form.list_suppliers"
_PATCH_BILL_ACCOUNTS = "saebooks_desktop.views.bill_form.list_expense_accounts"
_PATCH_BILL_TAX = "saebooks_desktop.views.bill_form.list_tax_codes"
_PATCH_INV_CONTACTS = "saebooks_desktop.views.invoice_form.list_contacts_for_invoice"
_PATCH_INV_ACCOUNTS = "saebooks_desktop.views.invoice_form.list_income_accounts"
_PATCH_INV_TAX = "saebooks_desktop.views.invoice_form.list_tax_codes"
_PATCH_EXTRACT = "saebooks_desktop.views.ai_extraction_widget.extract_document"


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_client():
    return MagicMock()


def _make_extract_widget(qapp, client=None):
    from saebooks_desktop.views.ai_extraction_widget import DocumentExtractWidget

    return DocumentExtractWidget(client or _make_client())


def _make_bill_form(qapp):
    from saebooks_desktop.views.bill_form import BillForm

    with (
        patch(_PATCH_BILL_SUPPLIERS, return_value=_SAMPLE_SUPPLIERS),
        patch(_PATCH_BILL_ACCOUNTS, return_value=_SAMPLE_ACCOUNTS),
        patch(_PATCH_BILL_TAX, return_value=_SAMPLE_TAX_CODES),
    ):
        return BillForm(_make_client())


def _make_invoice_form(qapp):
    from saebooks_desktop.views.invoice_form import InvoiceForm

    with (
        patch(_PATCH_INV_CONTACTS, return_value=_SAMPLE_CONTACTS),
        patch(_PATCH_INV_ACCOUNTS, return_value=_SAMPLE_ACCOUNTS),
        patch(_PATCH_INV_TAX, return_value=_SAMPLE_TAX_CODES),
    ):
        return InvoiceForm(_make_client())


# ===========================================================================
# 1. Service layer — extract_document
# ===========================================================================


class TestExtractDocumentService:
    def test_raises_value_error_for_missing_file(self, tmp_path):
        from saebooks_desktop.services.ai_extraction import extract_document

        client = MagicMock()
        client._base_url = "http://localhost:8000"
        client._token = "tok"
        client._timeout = 10.0

        with pytest.raises(ValueError, match="File not found"):
            extract_document(client, tmp_path / "nonexistent.pdf")

    def test_multipart_upload_posts_to_correct_path(self, tmp_path):
        """extract_document opens the file and POSTs to /api/v1/documents/extract."""
        from saebooks_desktop.services.ai_extraction import extract_document

        pdf = tmp_path / "invoice.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")

        client = MagicMock()
        client._base_url = "http://localhost:8000"
        client._token = "tok"
        client._timeout = 10.0

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = _HIGH_CONF_RESULT

        with patch("httpx.Client") as mock_httpx:
            mock_ctx = MagicMock()
            mock_httpx.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_httpx.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.post.return_value = mock_response

            result = extract_document(client, pdf)

        assert result == _HIGH_CONF_RESULT
        mock_ctx.post.assert_called_once()
        call_args = mock_ctx.post.call_args
        assert call_args[0][0] == "/api/v1/documents/extract"
        assert "files" in call_args[1]

    def test_api_error_raised_on_non_2xx(self, tmp_path):
        from saebooks_desktop.services.ai_extraction import extract_document
        from saebooks_desktop.services.api_client import APIError

        pdf = tmp_path / "bad.pdf"
        pdf.write_bytes(b"%PDF")

        client = MagicMock()
        client._base_url = "http://localhost:8000"
        client._token = "tok"
        client._timeout = 10.0

        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status_code = 422
        mock_response.text = "Unprocessable Entity"

        with patch("httpx.Client") as mock_httpx:
            mock_ctx = MagicMock()
            mock_httpx.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_httpx.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.post.return_value = mock_response

            with pytest.raises(APIError):
                extract_document(client, pdf)

    def test_server_offline_error_on_transport_error(self, tmp_path):
        import httpx as _httpx

        from saebooks_desktop.services.ai_extraction import extract_document
        from saebooks_desktop.services.api_client import ServerOfflineError

        pdf = tmp_path / "offline.pdf"
        pdf.write_bytes(b"%PDF")

        client = MagicMock()
        client._base_url = "http://localhost:8000"
        client._token = "tok"
        client._timeout = 10.0

        with patch("httpx.Client") as mock_httpx:
            mock_ctx = MagicMock()
            mock_httpx.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_httpx.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.post.side_effect = _httpx.ConnectError("refused")

            with pytest.raises(ServerOfflineError):
                extract_document(client, pdf)


# ===========================================================================
# 2. Widget — DocumentExtractWidget
# ===========================================================================


class TestDocumentExtractWidget:
    def test_renders_without_error(self, qapp):
        w = _make_extract_widget(qapp)
        assert w is not None

    def test_extract_button_initially_disabled(self, qapp):
        w = _make_extract_widget(qapp)
        assert not w._extract_btn.isEnabled()

    def test_path_label_initial_text(self, qapp):
        w = _make_extract_widget(qapp)
        assert w._path_label.text() == "No file selected"

    def test_browse_sets_path_label(self, qapp, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF")

        w = _make_extract_widget(qapp)
        with patch(
            "saebooks_desktop.views.ai_extraction_widget.QFileDialog.getOpenFileName",
            return_value=(str(pdf), ""),
        ):
            w._on_browse()

        assert w._path_label.text() == "test.pdf"
        assert w._extract_btn.isEnabled()

    def test_browse_cancel_leaves_state_unchanged(self, qapp):
        w = _make_extract_widget(qapp)
        with patch(
            "saebooks_desktop.views.ai_extraction_widget.QFileDialog.getOpenFileName",
            return_value=("", ""),
        ):
            w._on_browse()
        assert w._path_label.text() == "No file selected"
        assert not w._extract_btn.isEnabled()

    def test_extract_calls_service_and_emits_signal(self, qapp, tmp_path):
        pdf = tmp_path / "invoice.pdf"
        pdf.write_bytes(b"%PDF")

        w = _make_extract_widget(qapp)
        # Simulate file already selected
        w._file_path = pdf
        w._extract_btn.setEnabled(True)

        received: list[dict] = []
        w.extraction_complete.connect(received.append)

        with patch(_PATCH_EXTRACT, return_value=_HIGH_CONF_RESULT):
            w._on_extract()

        assert len(received) == 1
        assert received[0]["invoice_number"] == "INV-9999"

    def test_extract_shows_confidence_label(self, qapp, tmp_path):
        pdf = tmp_path / "conf.pdf"
        pdf.write_bytes(b"%PDF")

        w = _make_extract_widget(qapp)
        w.show()
        w._file_path = pdf
        w._extract_btn.setEnabled(True)

        with patch(_PATCH_EXTRACT, return_value=_HIGH_CONF_RESULT):
            w._on_extract()

        assert w._confidence_label.isVisible()
        assert "92%" in w._confidence_label.text()

    def test_low_confidence_confidence_label_is_orange(self, qapp, tmp_path):
        pdf = tmp_path / "low.pdf"
        pdf.write_bytes(b"%PDF")

        w = _make_extract_widget(qapp)
        w._file_path = pdf
        w._extract_btn.setEnabled(True)

        with patch(_PATCH_EXTRACT, return_value=_LOW_CONF_RESULT):
            w._on_extract()

        # orange colour is indicated in stylesheet
        assert "e65100" in w._confidence_label.styleSheet()

    def test_api_error_shows_error_label(self, qapp, tmp_path):
        from saebooks_desktop.services.api_client import APIError

        pdf = tmp_path / "err.pdf"
        pdf.write_bytes(b"%PDF")

        w = _make_extract_widget(qapp)
        w.show()
        w._file_path = pdf
        w._extract_btn.setEnabled(True)

        with patch(_PATCH_EXTRACT, side_effect=APIError("Server error", 500)):
            w._on_extract()

        assert w._error_label.isVisible()
        assert "Server error" in w._error_label.text()

    def test_api_error_does_not_emit_signal(self, qapp, tmp_path):
        from saebooks_desktop.services.api_client import APIError

        pdf = tmp_path / "nosig.pdf"
        pdf.write_bytes(b"%PDF")

        w = _make_extract_widget(qapp)
        w._file_path = pdf
        w._extract_btn.setEnabled(True)

        received: list[dict] = []
        w.extraction_complete.connect(received.append)

        with patch(_PATCH_EXTRACT, side_effect=APIError("fail", 500)):
            w._on_extract()

        assert received == []

    def test_progress_bar_hidden_after_successful_extract(self, qapp, tmp_path):
        pdf = tmp_path / "prog.pdf"
        pdf.write_bytes(b"%PDF")

        w = _make_extract_widget(qapp)
        w._file_path = pdf
        w._extract_btn.setEnabled(True)

        with patch(_PATCH_EXTRACT, return_value=_HIGH_CONF_RESULT):
            w._on_extract()

        assert not w._progress.isVisible()


# ===========================================================================
# 3. BillForm — AI extraction pre-fill
# ===========================================================================


class TestBillFormAIExtraction:
    def test_ai_group_present_and_collapsed(self, qapp):
        form = _make_bill_form(qapp)
        assert hasattr(form, "_ai_group")
        # Checkable QGroupBox: unchecked = collapsed
        assert not form._ai_group.isChecked()

    def test_extraction_complete_prefills_reference(self, qapp):
        form = _make_bill_form(qapp)
        form._on_extraction_complete(_HIGH_CONF_RESULT)
        assert form._reference_edit.text() == "INV-9999"

    def test_extraction_complete_prefills_issue_date(self, qapp):
        from PySide6.QtCore import QDate

        form = _make_bill_form(qapp)
        form._on_extraction_complete(_HIGH_CONF_RESULT)
        assert form._issue_date.date() == QDate.fromString("2026-04-25", "yyyy-MM-dd")

    def test_extraction_complete_prefills_due_date(self, qapp):
        from PySide6.QtCore import QDate

        form = _make_bill_form(qapp)
        form._on_extraction_complete(_HIGH_CONF_RESULT)
        assert form._due_date.date() == QDate.fromString("2026-05-25", "yyyy-MM-dd")

    def test_extraction_complete_prefills_line_items(self, qapp):
        form = _make_bill_form(qapp)
        form._on_extraction_complete(_HIGH_CONF_RESULT)
        assert form.line_count() == 1
        desc_w = form._lines_table.cellWidget(0, 0)
        assert desc_w.text() == "Office supplies"

    def test_extraction_complete_matches_vendor_to_supplier(self, qapp):
        form = _make_bill_form(qapp)
        form._on_extraction_complete(_HIGH_CONF_RESULT)
        # "Acme Supplies" should match supplier combo item "Acme Supplies"
        assert form._contact_combo.currentData() == _UUID_SUPPLIER

    def test_low_confidence_shows_banner(self, qapp):
        form = _make_bill_form(qapp)
        form._on_extraction_complete(_LOW_CONF_RESULT)
        # Use not isHidden() — parent QGroupBox may be collapsed in offscreen tests
        assert not form._ai_low_conf_banner.isHidden()

    def test_high_confidence_hides_banner(self, qapp):
        form = _make_bill_form(qapp)
        # First show it with low confidence, then clear with high
        form._on_extraction_complete(_LOW_CONF_RESULT)
        assert not form._ai_low_conf_banner.isHidden()
        form._on_extraction_complete(_HIGH_CONF_RESULT)
        assert form._ai_low_conf_banner.isHidden()
