"""Tests for MainWindow push/pop navigation between list and detail views.

Verifies that:
  - invoice_selected signal causes the sales stack to show InvoiceDetailView
  - back_requested from InvoiceDetailView pops back to InvoicesView
  - bill_selected signal causes the purchases stack to show BillDetailView
  - back_requested from BillDetailView pops back to BillsView

All API calls are mocked so no server is needed.
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
# Helper: build MainWindow with all API calls mocked
# ---------------------------------------------------------------------------

_MOCK_PATCH_TARGETS = [
    "saebooks_desktop.views.invoices.list_invoices",
    "saebooks_desktop.views.bills.list_bills",
    "saebooks_desktop.services.api_client.APIClient.resolve_transport",
    "saebooks_desktop.cache.sync.SyncEngine.start",
    "saebooks_desktop.cache.sync.SyncEngine.isRunning",
]


def _make_window(qapp):
    from unittest.mock import MagicMock

    from saebooks_desktop.main_window import MainWindow

    # Mock transport to avoid real HTTP
    mock_transport = MagicMock()
    mock_transport.is_reachable.return_value = False

    with (
        patch("saebooks_desktop.views.invoices.list_invoices", return_value=[]),
        patch("saebooks_desktop.views.bills.list_bills", return_value=[]),
        patch(
            "saebooks_desktop.services.api_client.APIClient.resolve_transport",
            return_value=mock_transport,
        ),
        patch(
            "saebooks_desktop.cache.sync.SyncEngine.isRunning",
            return_value=False,
        ),
    ):
        window = MainWindow()
    return window


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInvoiceNavigation:
    def test_invoice_detail_view_exists_on_window(self, qapp) -> None:
        """MainWindow must expose _invoice_detail_view after construction."""
        from saebooks_desktop.views.invoice_detail import InvoiceDetailView

        window = _make_window(qapp)
        assert hasattr(window, "_invoice_detail_view")
        assert isinstance(window._invoice_detail_view, InvoiceDetailView)

    def test_invoices_view_exists_on_window(self, qapp) -> None:
        from saebooks_desktop.views.invoices import InvoicesView

        window = _make_window(qapp)
        assert hasattr(window, "_invoices_view")
        assert isinstance(window._invoices_view, InvoicesView)

    def test_sales_stack_starts_on_list_view(self, qapp) -> None:
        """Sales nested stack must start with InvoicesView (index 0)."""
        from saebooks_desktop.views.invoices import InvoicesView

        window = _make_window(qapp)
        current = window._sales_stack.currentWidget()
        assert isinstance(current, InvoicesView)

    def test_invoice_selected_shows_detail_view(self, qapp) -> None:
        """invoice_selected signal must push InvoiceDetailView to front."""
        from saebooks_desktop.views.invoice_detail import InvoiceDetailView

        window = _make_window(qapp)

        with patch(
            "saebooks_desktop.views.invoice_detail.get_invoice",
            return_value={
                "id": "inv-001",
                "number": "INV-0001",
                "status": "posted",
                "contact_name": "Test Co",
                "issue_date": "2024-01-01",
                "due_date": "2024-02-01",
                "subtotal": "100",
                "tax_total": "10",
                "total": "110",
                "lines": [],
            },
        ):
            window._invoices_view.invoice_selected.emit("inv-001")

        assert isinstance(window._sales_stack.currentWidget(), InvoiceDetailView)

    def test_back_from_invoice_detail_restores_list(self, qapp) -> None:
        """back_requested from InvoiceDetailView must restore InvoicesView."""
        from saebooks_desktop.views.invoices import InvoicesView

        window = _make_window(qapp)

        with patch(
            "saebooks_desktop.views.invoice_detail.get_invoice",
            return_value={
                "id": "inv-001",
                "number": "INV-0001",
                "status": "draft",
                "contact_name": "Test Co",
                "issue_date": "2024-01-01",
                "due_date": "2024-02-01",
                "subtotal": "100",
                "tax_total": "10",
                "total": "110",
                "lines": [],
            },
        ):
            window._invoices_view.invoice_selected.emit("inv-001")

        # Now fire back
        window._invoice_detail_view.back_requested.emit()
        assert isinstance(window._sales_stack.currentWidget(), InvoicesView)


class TestInvoiceFormNavigation:
    """New Invoice and Edit navigation via InvoiceForm (E/12)."""

    _FORM_REF_PATCHES = [
        "saebooks_desktop.views.invoice_form.list_contacts_for_invoice",
        "saebooks_desktop.views.invoice_form.list_income_accounts",
        "saebooks_desktop.views.invoice_form.list_tax_codes",
    ]

    def _make_window_with_form_mocked(self, qapp):
        """Build MainWindow with both list-view and form reference-data mocked."""
        from unittest.mock import MagicMock, patch

        from saebooks_desktop.main_window import MainWindow

        mock_transport = MagicMock()
        mock_transport.is_reachable.return_value = False

        with (
            patch("saebooks_desktop.views.invoices.list_invoices", return_value=[]),
            patch("saebooks_desktop.views.bills.list_bills", return_value=[]),
            patch(
                "saebooks_desktop.services.api_client.APIClient.resolve_transport",
                return_value=mock_transport,
            ),
            patch(
                "saebooks_desktop.cache.sync.SyncEngine.isRunning",
                return_value=False,
            ),
            patch(
                "saebooks_desktop.views.invoice_form.list_contacts_for_invoice",
                return_value=[],
            ),
            patch("saebooks_desktop.views.invoice_form.list_income_accounts", return_value=[]),
            patch("saebooks_desktop.views.invoice_form.list_tax_codes", return_value=[]),
        ):
            window = MainWindow()
        return window

    def test_new_invoice_button_shows_form(self, qapp) -> None:
        """Clicking New Invoice in InvoicesView pushes InvoiceForm to front."""
        from saebooks_desktop.views.invoice_form import InvoiceForm

        window = self._make_window_with_form_mocked(qapp)

        with (
            patch("saebooks_desktop.views.invoice_form.list_contacts_for_invoice", return_value=[]),
            patch("saebooks_desktop.views.invoice_form.list_income_accounts", return_value=[]),
            patch("saebooks_desktop.views.invoice_form.list_tax_codes", return_value=[]),
        ):
            window._invoices_view.new_invoice_requested.emit()

        assert isinstance(window._sales_stack.currentWidget(), InvoiceForm)

    def test_edit_button_shows_form_with_invoice_id(self, qapp) -> None:
        """edit_requested signal from InvoiceDetailView pushes InvoiceForm."""
        from saebooks_desktop.views.invoice_form import InvoiceForm

        window = self._make_window_with_form_mocked(qapp)

        with (
            patch(
                "saebooks_desktop.views.invoice_detail.get_invoice",
                return_value={
                    "id": "inv-edit",
                    "number": "INV-0001",
                    "status": "draft",
                    "contact_name": "Acme",
                    "issue_date": "2024-01-01",
                    "due_date": "2024-02-01",
                    "subtotal": "100",
                    "tax_total": "10",
                    "total": "110",
                    "lines": [],
                },
            ),
            patch("saebooks_desktop.views.invoice_form.list_contacts_for_invoice", return_value=[]),
            patch("saebooks_desktop.views.invoice_form.list_income_accounts", return_value=[]),
            patch("saebooks_desktop.views.invoice_form.list_tax_codes", return_value=[]),
            patch("saebooks_desktop.views.invoice_form.get_invoice", return_value={
                "id": "inv-edit",
                "number": "INV-0001",
                "contact_id": None,
                "issue_date": "2024-01-01",
                "due_date": "2024-02-01",
                "version": 1,
                "lines": [],
            }),
        ):
            # First navigate to detail
            window._invoices_view.invoice_selected.emit("inv-edit")
            # Then trigger edit
            window._invoice_detail_view.edit_requested.emit("inv-edit")

        assert isinstance(window._sales_stack.currentWidget(), InvoiceForm)

    def test_form_cancel_returns_to_list_from_new(self, qapp) -> None:
        """Cancelling a new-invoice form returns to InvoicesView."""
        from saebooks_desktop.views.invoices import InvoicesView

        window = self._make_window_with_form_mocked(qapp)

        with (
            patch("saebooks_desktop.views.invoice_form.list_contacts_for_invoice", return_value=[]),
            patch("saebooks_desktop.views.invoice_form.list_income_accounts", return_value=[]),
            patch("saebooks_desktop.views.invoice_form.list_tax_codes", return_value=[]),
        ):
            window._invoices_view.new_invoice_requested.emit()

        # Cancel the form
        form = window._sales_stack.currentWidget()
        form.cancelled.emit()

        assert isinstance(window._sales_stack.currentWidget(), InvoicesView)

    def test_form_saved_returns_to_detail(self, qapp) -> None:
        """invoice_saved signal from form loads and shows InvoiceDetailView."""
        from saebooks_desktop.views.invoice_detail import InvoiceDetailView

        window = self._make_window_with_form_mocked(qapp)

        with (
            patch("saebooks_desktop.views.invoice_form.list_contacts_for_invoice", return_value=[]),
            patch("saebooks_desktop.views.invoice_form.list_income_accounts", return_value=[]),
            patch("saebooks_desktop.views.invoice_form.list_tax_codes", return_value=[]),
        ):
            window._invoices_view.new_invoice_requested.emit()

        form = window._sales_stack.currentWidget()

        # Simulate successful save
        with patch(
            "saebooks_desktop.views.invoice_detail.get_invoice",
            return_value={
                "id": "inv-saved",
                "number": "INV-0099",
                "status": "draft",
                "contact_name": "Acme",
                "issue_date": "2024-01-01",
                "due_date": "2024-02-01",
                "subtotal": "0",
                "tax_total": "0",
                "total": "0",
                "lines": [],
            },
        ):
            form.invoice_saved.emit("inv-saved")

        assert isinstance(window._sales_stack.currentWidget(), InvoiceDetailView)


class TestBillNavigation:
    def test_bill_detail_view_exists_on_window(self, qapp) -> None:
        from saebooks_desktop.views.bill_detail import BillDetailView

        window = _make_window(qapp)
        assert hasattr(window, "_bill_detail_view")
        assert isinstance(window._bill_detail_view, BillDetailView)

    def test_bills_view_exists_on_window(self, qapp) -> None:
        from saebooks_desktop.views.bills import BillsView

        window = _make_window(qapp)
        assert hasattr(window, "_bills_view")
        assert isinstance(window._bills_view, BillsView)

    def test_purchases_stack_starts_on_list_view(self, qapp) -> None:
        from saebooks_desktop.views.bills import BillsView

        window = _make_window(qapp)
        current = window._purchases_stack.currentWidget()
        assert isinstance(current, BillsView)

    def test_bill_selected_shows_detail_view(self, qapp) -> None:
        from saebooks_desktop.views.bill_detail import BillDetailView

        window = _make_window(qapp)

        with patch(
            "saebooks_desktop.views.bill_detail.get_bill",
            return_value={
                "id": "bill-001",
                "number": "BILL-0001",
                "status": "posted",
                "supplier_name": "Acme Supplies",
                "issue_date": "2024-01-01",
                "due_date": "2024-02-01",
                "subtotal": "200",
                "tax_total": "20",
                "total": "220",
                "lines": [],
            },
        ):
            window._bills_view.bill_selected.emit("bill-001")

        assert isinstance(window._purchases_stack.currentWidget(), BillDetailView)

    def test_back_from_bill_detail_restores_list(self, qapp) -> None:
        from saebooks_desktop.views.bills import BillsView

        window = _make_window(qapp)

        with patch(
            "saebooks_desktop.views.bill_detail.get_bill",
            return_value={
                "id": "bill-001",
                "number": "BILL-0001",
                "status": "draft",
                "supplier_name": "Acme Supplies",
                "issue_date": "2024-01-01",
                "due_date": "2024-02-01",
                "subtotal": "200",
                "tax_total": "20",
                "total": "220",
                "lines": [],
            },
        ):
            window._bills_view.bill_selected.emit("bill-001")

        window._bill_detail_view.back_requested.emit()
        assert isinstance(window._purchases_stack.currentWidget(), BillsView)


class TestBillFormNavigation:
    """New Bill and Edit navigation via BillForm (E/13)."""

    _BILL_DATA = {
        "id": "bill-001",
        "number": "BILL-0001",
        "status": "draft",
        "supplier_name": "Acme Supplies",
        "issue_date": "2024-01-01",
        "due_date": "2024-02-01",
        "subtotal": "200",
        "tax_total": "20",
        "total": "220",
        "lines": [],
    }

    def _make_window_with_form_mocked(self, qapp):
        from unittest.mock import MagicMock

        from saebooks_desktop.main_window import MainWindow

        mock_transport = MagicMock()
        mock_transport.is_reachable.return_value = False

        with (
            patch("saebooks_desktop.views.invoices.list_invoices", return_value=[]),
            patch("saebooks_desktop.views.bills.list_bills", return_value=[]),
            patch(
                "saebooks_desktop.services.api_client.APIClient.resolve_transport",
                return_value=mock_transport,
            ),
            patch("saebooks_desktop.cache.sync.SyncEngine.isRunning", return_value=False),
            patch("saebooks_desktop.views.bill_form.list_suppliers", return_value=[]),
            patch("saebooks_desktop.views.bill_form.list_expense_accounts", return_value=[]),
            patch("saebooks_desktop.views.bill_form.list_tax_codes", return_value=[]),
        ):
            window = MainWindow()
        return window

    def test_new_bill_button_shows_form(self, qapp) -> None:
        """Clicking New Bill in BillsView pushes BillForm to front."""
        from saebooks_desktop.views.bill_form import BillForm

        window = self._make_window_with_form_mocked(qapp)

        with (
            patch("saebooks_desktop.views.bill_form.list_suppliers", return_value=[]),
            patch("saebooks_desktop.views.bill_form.list_expense_accounts", return_value=[]),
            patch("saebooks_desktop.views.bill_form.list_tax_codes", return_value=[]),
        ):
            window._bills_view.new_bill_requested.emit()

        assert isinstance(window._purchases_stack.currentWidget(), BillForm)

    def test_edit_button_shows_form_with_bill_id(self, qapp) -> None:
        """edit_requested signal from BillDetailView pushes BillForm."""
        from saebooks_desktop.views.bill_form import BillForm

        window = self._make_window_with_form_mocked(qapp)

        with (
            patch("saebooks_desktop.views.bill_detail.get_bill", return_value=self._BILL_DATA),
            patch("saebooks_desktop.views.bill_form.list_suppliers", return_value=[]),
            patch("saebooks_desktop.views.bill_form.list_expense_accounts", return_value=[]),
            patch("saebooks_desktop.views.bill_form.list_tax_codes", return_value=[]),
            patch(
                "saebooks_desktop.views.bill_form.get_bill",
                return_value={
                    "id": "bill-001",
                    "number": "BILL-0001",
                    "contact_id": None,
                    "issue_date": "2024-01-01",
                    "due_date": "2024-02-01",
                    "version": 1,
                    "lines": [],
                },
            ),
        ):
            window._bills_view.bill_selected.emit("bill-001")
            window._bill_detail_view.edit_requested.emit("bill-001")

        assert isinstance(window._purchases_stack.currentWidget(), BillForm)

    def test_form_cancel_returns_to_list_from_new(self, qapp) -> None:
        """Cancelling a new-bill form returns to BillsView."""
        from saebooks_desktop.views.bills import BillsView

        window = self._make_window_with_form_mocked(qapp)

        with (
            patch("saebooks_desktop.views.bill_form.list_suppliers", return_value=[]),
            patch("saebooks_desktop.views.bill_form.list_expense_accounts", return_value=[]),
            patch("saebooks_desktop.views.bill_form.list_tax_codes", return_value=[]),
        ):
            window._bills_view.new_bill_requested.emit()

        form = window._purchases_stack.currentWidget()
        form.cancelled.emit()

        assert isinstance(window._purchases_stack.currentWidget(), BillsView)

    def test_form_saved_returns_to_detail(self, qapp) -> None:
        """bill_saved signal from form loads and shows BillDetailView."""
        from saebooks_desktop.views.bill_detail import BillDetailView

        window = self._make_window_with_form_mocked(qapp)

        with (
            patch("saebooks_desktop.views.bill_form.list_suppliers", return_value=[]),
            patch("saebooks_desktop.views.bill_form.list_expense_accounts", return_value=[]),
            patch("saebooks_desktop.views.bill_form.list_tax_codes", return_value=[]),
        ):
            window._bills_view.new_bill_requested.emit()

        form = window._purchases_stack.currentWidget()

        with patch(
            "saebooks_desktop.views.bill_detail.get_bill",
            return_value={
                "id": "bill-saved",
                "number": "BILL-0099",
                "status": "draft",
                "supplier_name": "Acme Supplies",
                "issue_date": "2024-01-01",
                "due_date": "2024-02-01",
                "subtotal": "0",
                "tax_total": "0",
                "total": "0",
                "lines": [],
            },
        ):
            form.bill_saved.emit("bill-saved")

        assert isinstance(window._purchases_stack.currentWidget(), BillDetailView)
