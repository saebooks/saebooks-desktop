"""Tests for InvoicesView — offscreen Qt, mocked API service layer.

All tests run without a real API server.  The service function
``saebooks_desktop.services.invoices.list_invoices`` is patched at the
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

_SAMPLE_INVOICES = [
    {
        "id": "inv-001",
        "number": "INV-0001",
        "contact_name": "Acme Corp",
        "issue_date": "2024-01-15",
        "due_date": "2024-02-15",
        "amount": "1500.00",
        "status": "posted",
    },
    {
        "id": "inv-002",
        "number": "INV-0002",
        "contact_name": "Beta Ltd",
        "issue_date": "2024-01-20",
        "due_date": "2024-02-20",
        "amount": "250.00",
        "status": "draft",
    },
    {
        "id": "inv-003",
        "number": "INV-0003",
        "contact_name": "Gamma Inc",
        "issue_date": "2024-01-25",
        "due_date": "2024-02-25",
        "amount": "800.00",
        "status": "voided",
    },
]


# ---------------------------------------------------------------------------
# Helper to build a view with a mocked list_invoices
# ---------------------------------------------------------------------------


def _make_view(qapp, items=None, side_effect=None):
    """Create InvoicesView with list_invoices patched to return *items*."""
    from saebooks_desktop.views.invoices import InvoicesView

    if side_effect is not None:
        with patch(
            "saebooks_desktop.views.invoices.list_invoices",
            side_effect=side_effect,
        ):
            return InvoicesView()
    else:
        with patch(
            "saebooks_desktop.views.invoices.list_invoices",
            return_value=items if items is not None else [],
        ):
            return InvoicesView()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInvoicesViewInstantiation:
    def test_instantiates_without_crash(self, qapp) -> None:
        """InvoicesView must create without raising when API is mocked."""
        view = _make_view(qapp, items=[])
        assert view is not None

    def test_has_table_model(self, qapp) -> None:
        """View must expose a QStandardItemModel on _model."""
        from PySide6.QtGui import QStandardItemModel

        view = _make_view(qapp, items=[])
        assert isinstance(view._model, QStandardItemModel)

    def test_has_six_columns(self, qapp) -> None:
        """Model must have 6 columns: Number, Contact, Issue Date, Due Date, Amount, Status."""
        view = _make_view(qapp, items=[])
        assert view._model.columnCount() == 6

    def test_column_headers(self, qapp) -> None:
        """Column headers must match the spec exactly."""
        expected = ["Number", "Contact", "Issue Date", "Due Date", "Amount", "Status"]
        view = _make_view(qapp, items=[])
        headers = [
            view._model.horizontalHeaderItem(i).text()
            for i in range(view._model.columnCount())
        ]
        assert headers == expected


class TestInvoicesViewModelPopulation:
    def test_row_count_matches_items(self, qapp) -> None:
        """Model must have one row per invoice returned by the service."""
        view = _make_view(qapp, items=_SAMPLE_INVOICES)
        assert view._model.rowCount() == 3

    def test_row_data_number_column(self, qapp) -> None:
        """First column must show the invoice number."""
        view = _make_view(qapp, items=_SAMPLE_INVOICES)
        assert view._model.item(0, 0).text() == "INV-0001"
        assert view._model.item(1, 0).text() == "INV-0002"

    def test_row_data_contact_column(self, qapp) -> None:
        """Second column must show the contact name."""
        view = _make_view(qapp, items=_SAMPLE_INVOICES)
        assert view._model.item(0, 1).text() == "Acme Corp"

    def test_row_data_status_column(self, qapp) -> None:
        """Sixth column must show the status string."""
        view = _make_view(qapp, items=_SAMPLE_INVOICES)
        assert view._model.item(0, 5).text() == "posted"
        assert view._model.item(1, 5).text() == "draft"
        assert view._model.item(2, 5).text() == "voided"

    def test_amount_right_aligned(self, qapp) -> None:
        """Amount column items must be right-aligned."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_INVOICES)
        amount_item = view._model.item(0, 4)
        alignment = amount_item.textAlignment()
        assert alignment & Qt.AlignmentFlag.AlignRight

    def test_invoice_id_stored_as_user_role(self, qapp) -> None:
        """The invoice id must be stored as UserRole on the number column item."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_INVOICES)
        stored_id = view._model.item(0, 0).data(Qt.ItemDataRole.UserRole)
        assert stored_id == "inv-001"

    def test_empty_state_zero_rows(self, qapp) -> None:
        """When service returns empty list, model must have 0 rows."""
        view = _make_view(qapp, items=[])
        assert view._model.rowCount() == 0


class TestInvoicesViewOffline:
    def test_offline_banner_shown_on_server_error(self, qapp) -> None:
        """Offline banner must be visible when service raises ServerOfflineError."""
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _make_view(qapp, side_effect=ServerOfflineError("offline"))
        assert not view._offline_label.isHidden()

    def test_offline_banner_hidden_when_data_loads(self, qapp) -> None:
        """Offline banner must be hidden when data loads successfully."""
        view = _make_view(qapp, items=_SAMPLE_INVOICES)
        assert view._offline_label.isHidden()


class TestInvoicesViewFilterToolbar:
    def test_has_status_combo(self, qapp) -> None:
        """View must expose a status filter QComboBox."""
        from PySide6.QtWidgets import QComboBox

        view = _make_view(qapp, items=[])
        assert isinstance(view._status_combo, QComboBox)

    def test_status_combo_options(self, qapp) -> None:
        """Status combo must contain All, Draft, Posted, Voided."""
        view = _make_view(qapp, items=[])
        options = [
            view._status_combo.itemText(i)
            for i in range(view._status_combo.count())
        ]
        assert options == ["All", "Draft", "Posted", "Voided"]

    def test_has_new_invoice_button(self, qapp) -> None:
        """View must expose a New Invoice QPushButton."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._new_btn, QPushButton)
        assert view._new_btn.text() == "New Invoice"

    def test_status_filter_triggers_reload(self, qapp) -> None:
        """Changing the status combo must trigger a fresh load (page reset to 1)."""
        from PySide6.QtWidgets import QApplication

        call_count = 0

        def _side_effect(client, page=1, page_size=50, **kwargs):
            nonlocal call_count
            call_count += 1
            return []

        with patch(
            "saebooks_desktop.views.invoices.list_invoices",
            side_effect=_side_effect,
        ):
            from saebooks_desktop.views.invoices import InvoicesView

            view = InvoicesView()
            before = call_count
            view._status_combo.setCurrentIndex(1)  # select "Draft"
            QApplication.processEvents()
            assert call_count > before, "list_invoices should have been called again"


class TestInvoicesViewDoubleClick:
    def test_double_click_emits_invoice_selected(self, qapp) -> None:
        """Double-clicking a row must emit invoice_selected with the invoice id."""
        view = _make_view(qapp, items=_SAMPLE_INVOICES)

        received: list[str] = []
        view.invoice_selected.connect(received.append)

        # Simulate double-click by calling the handler directly with row 0 index
        index = view._model.index(0, 0)
        view._on_double_click(index)

        assert received == ["inv-001"]

    def test_double_click_second_row(self, qapp) -> None:
        """Double-clicking row 1 must emit the id of the second invoice."""
        view = _make_view(qapp, items=_SAMPLE_INVOICES)

        received: list[str] = []
        view.invoice_selected.connect(received.append)

        index = view._model.index(1, 0)
        view._on_double_click(index)

        assert received == ["inv-002"]

    def test_new_invoice_signal_emitted(self, qapp) -> None:
        """Clicking New Invoice must emit new_invoice_requested."""
        view = _make_view(qapp, items=[])

        triggered = []
        view.new_invoice_requested.connect(lambda: triggered.append(True))
        view._new_btn.click()

        assert triggered == [True]


class TestInvoicesViewPagination:
    def test_load_more_button_exists(self, qapp) -> None:
        """View must expose a Load more QPushButton."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._load_more_btn, QPushButton)

    def test_load_more_disabled_when_fewer_than_page_size(self, qapp) -> None:
        """Load more must be disabled when fewer than 50 items are returned."""
        view = _make_view(qapp, items=_SAMPLE_INVOICES)  # only 3 items
        assert not view._load_more_btn.isEnabled()

    def test_load_more_appends_rows(self, qapp) -> None:
        """Clicking Load more must append the next page to the existing rows."""
        # Build exactly 50 items for page 1 so the view treats it as a full page
        # (fewer than page_size would disable Load more).
        _PAGE_SIZE = 50
        page_1 = (_SAMPLE_INVOICES * 20)[:_PAGE_SIZE]  # exactly 50 items

        extra_invoice = {
            "id": "inv-extra",
            "number": "INV-EXTRA",
            "contact_name": "Delta",
            "issue_date": "2024-02-01",
            "due_date": "2024-03-01",
            "amount": "100.00",
            "status": "draft",
        }

        with patch(
            "saebooks_desktop.views.invoices.list_invoices", return_value=page_1
        ):
            from saebooks_desktop.views.invoices import InvoicesView

            view = InvoicesView()

        rows_after_first_load = view._model.rowCount()
        assert rows_after_first_load == _PAGE_SIZE

        with patch(
            "saebooks_desktop.views.invoices.list_invoices",
            return_value=[extra_invoice],
        ):
            view._on_load_more()

        assert view._model.rowCount() == rows_after_first_load + 1
        assert view._model.item(rows_after_first_load, 0).text() == "INV-EXTRA"
