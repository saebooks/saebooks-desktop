"""Tests for Stripe payment link button on InvoiceDetailView — E/21.

Eight tests:
1. test_payment_link_btn_present           — button exists after instantiation
2. test_payment_link_btn_disabled_for_draft — button disabled for DRAFT invoice
3. test_payment_link_btn_disabled_for_voided — button disabled for VOIDED invoice
4. test_payment_link_btn_enabled_for_posted  — button enabled for POSTED invoice
5. test_payment_link_happy_path_shows_dialog — success: QDialog appears with URL
6. test_payment_link_503_shows_error_banner  — 503: inline error banner shown
7. test_payment_link_422_shows_error_banner  — 422: inline error banner shown
8. test_generate_payment_link_service        — service function calls correct path
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
# Sample invoice data
# ---------------------------------------------------------------------------

_UUID_CONTACT = "a1b2c3d4-0000-0000-0000-000000000003"

_SAMPLE_INVOICE_POSTED = {
    "id": "inv-stripe-01",
    "number": "INV-0055",
    "contact_id": _UUID_CONTACT,
    "contact_name": "Stripe Test Corp",
    "issue_date": "2026-04-01",
    "due_date": "2026-05-01",
    "status": "posted",
    "subtotal": "1000.00",
    "tax_total": "100.00",
    "total": "1100.00",
    "lines": [],
}

_SAMPLE_INVOICE_DRAFT = {
    **_SAMPLE_INVOICE_POSTED,
    "id": "inv-stripe-02",
    "status": "draft",
}

_SAMPLE_INVOICE_VOIDED = {
    **_SAMPLE_INVOICE_POSTED,
    "id": "inv-stripe-03",
    "status": "voided",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_view(qapp, data=None, side_effect=None):
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


class TestPaymentLinkButton:
    def test_payment_link_btn_present(self, qapp) -> None:
        """Button exists in the toolbar after instantiation."""
        from PySide6.QtWidgets import QPushButton

        from saebooks_desktop.views.invoice_detail import InvoiceDetailView

        view = InvoiceDetailView()
        assert isinstance(view._payment_link_btn, QPushButton)

    def test_payment_link_btn_disabled_for_draft(self, qapp) -> None:
        """Generate Payment Link is disabled for DRAFT invoices."""
        view = _load_view(qapp, data=_SAMPLE_INVOICE_DRAFT)
        assert not view._payment_link_btn.isEnabled()

    def test_payment_link_btn_disabled_for_voided(self, qapp) -> None:
        """Generate Payment Link is disabled for VOIDED invoices."""
        view = _load_view(qapp, data=_SAMPLE_INVOICE_VOIDED)
        assert not view._payment_link_btn.isEnabled()

    def test_payment_link_btn_enabled_for_posted(self, qapp) -> None:
        """Generate Payment Link is enabled for POSTED invoices."""
        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)
        assert view._payment_link_btn.isEnabled()


class TestPaymentLinkHappyPath:
    def test_payment_link_happy_path_shows_dialog(self, qapp) -> None:
        """On success, _PaymentLinkDialog is exec'd and no error banner is shown."""
        from saebooks_desktop.views.invoice_detail import _PaymentLinkDialog

        _URL = "https://buy.stripe.com/test_live_abc"
        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)

        dlg_instances: list[_PaymentLinkDialog] = []

        def _fake_exec(self_dlg):
            dlg_instances.append(self_dlg)

        with (
            patch(
                "saebooks_desktop.views.invoice_detail.generate_payment_link",
                return_value=_URL,
            ),
            patch.object(_PaymentLinkDialog, "exec", _fake_exec),
        ):
            view._on_payment_link_clicked()

        assert len(dlg_instances) == 1
        # Error banner must be hidden (isHidden matches setVisible(False))
        assert view._payment_link_error.isHidden()


class TestPaymentLinkErrors:
    def test_payment_link_503_shows_error_banner(self, qapp) -> None:
        """On APIError(503), error banner shows 'Stripe not configured'."""
        from saebooks_desktop.services.api_client import APIError

        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)

        with patch(
            "saebooks_desktop.views.invoice_detail.generate_payment_link",
            side_effect=APIError("Stripe not configured", status_code=503),
        ):
            view._on_payment_link_clicked()

        assert not view._payment_link_error.isHidden()
        assert "Stripe not configured" in view._payment_link_error.text()
        assert "STRIPE_SECRET_KEY" in view._payment_link_error.text()

    def test_payment_link_422_shows_error_banner(self, qapp) -> None:
        """On APIError(422), error banner shows outstanding balance message."""
        from saebooks_desktop.services.api_client import APIError

        view = _load_view(qapp, data=_SAMPLE_INVOICE_POSTED)

        with patch(
            "saebooks_desktop.views.invoice_detail.generate_payment_link",
            side_effect=APIError("Unprocessable", status_code=422),
        ):
            view._on_payment_link_clicked()

        assert not view._payment_link_error.isHidden()
        assert "outstanding balance" in view._payment_link_error.text()


class TestGeneratePaymentLinkService:
    def test_generate_payment_link_calls_correct_path(self) -> None:
        """generate_payment_link POSTs to the correct API path and returns the URL."""
        mock_client = MagicMock()
        mock_client.post.return_value = {"url": "https://buy.stripe.com/srv_test"}

        from saebooks_desktop.services.stripe_links import generate_payment_link

        url = generate_payment_link(mock_client, "inv-abc-123")

        mock_client.post.assert_called_once_with(
            "/api/v1/invoices/inv-abc-123/stripe-payment-link"
        )
        assert url == "https://buy.stripe.com/srv_test"
