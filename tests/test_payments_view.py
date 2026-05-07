"""Tests for PaymentsView — offscreen Qt, mocked API service layer.

All tests run without a real API server.  The service function
``saebooks_desktop.services.payments.list_payments`` is patched at the
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

_SAMPLE_PAYMENTS = [
    {
        "id": "pmt-001",
        "date": "2024-01-15",
        "reference": "PMT-0001",
        "contact_name": "Acme Corp",
        "direction": "in",
        "amount": "1500.00",
        "method": "bank_transfer",
        "status": "cleared",
    },
    {
        "id": "pmt-002",
        "date": "2024-01-18",
        "reference": "PMT-0002",
        "contact_name": "Office Supplies Co",
        "direction": "out",
        "amount": "350.00",
        "method": "bpay",
        "status": "cleared",
    },
    {
        "id": "pmt-003",
        "date": "2024-01-22",
        "reference": "PMT-0003",
        "contact_name": "Beta Ltd",
        "direction": "in",
        "amount": "800.00",
        "method": "direct_debit",
        "status": "pending",
    },
]


# ---------------------------------------------------------------------------
# Helper to build a view with a mocked list_payments
# ---------------------------------------------------------------------------


def _make_view(qapp, items=None, side_effect=None):
    """Create PaymentsView with list_payments patched to return *items*."""
    from saebooks_desktop.views.payments import PaymentsView

    if side_effect is not None:
        with patch(
            "saebooks_desktop.views.payments.list_payments",
            side_effect=side_effect,
        ):
            return PaymentsView()
    else:
        with patch(
            "saebooks_desktop.views.payments.list_payments",
            return_value=items if items is not None else [],
        ):
            return PaymentsView()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPaymentsViewInstantiation:
    def test_instantiates_without_crash(self, qapp) -> None:
        """PaymentsView must create without raising when API is mocked."""
        view = _make_view(qapp, items=[])
        assert view is not None

    def test_has_table_model(self, qapp) -> None:
        """View must expose a QStandardItemModel on _model."""
        from PySide6.QtGui import QStandardItemModel

        view = _make_view(qapp, items=[])
        assert isinstance(view._model, QStandardItemModel)

    def test_has_seven_columns(self, qapp) -> None:
        """Model must have 7 columns."""
        view = _make_view(qapp, items=[])
        assert view._model.columnCount() == 7

    def test_column_headers(self, qapp) -> None:
        """Column headers must match the spec exactly."""
        expected = [
            "Date", "Reference", "Contact", "Direction",
            "Amount", "Method", "Status",
        ]
        view = _make_view(qapp, items=[])
        headers = [
            view._model.horizontalHeaderItem(i).text()
            for i in range(view._model.columnCount())
        ]
        assert headers == expected

    def test_uses_qtableview(self, qapp) -> None:
        """View must use QTableView as its primary widget."""
        from PySide6.QtWidgets import QTableView

        view = _make_view(qapp, items=[])
        assert isinstance(view._table, QTableView)


class TestPaymentsViewModelPopulation:
    def test_row_count_matches_items(self, qapp) -> None:
        """Model must have one row per payment returned by the service."""
        view = _make_view(qapp, items=_SAMPLE_PAYMENTS)
        assert view._model.rowCount() == 3

    def test_row_data_date_column(self, qapp) -> None:
        """First column must show the payment date."""
        view = _make_view(qapp, items=_SAMPLE_PAYMENTS)
        assert view._model.item(0, 0).text() == "2024-01-15"
        assert view._model.item(1, 0).text() == "2024-01-18"

    def test_row_data_reference_column(self, qapp) -> None:
        """Second column must show the reference."""
        view = _make_view(qapp, items=_SAMPLE_PAYMENTS)
        assert view._model.item(0, 1).text() == "PMT-0001"

    def test_row_data_contact_column(self, qapp) -> None:
        """Third column must show the contact name."""
        view = _make_view(qapp, items=_SAMPLE_PAYMENTS)
        assert view._model.item(0, 2).text() == "Acme Corp"

    def test_row_data_direction_column(self, qapp) -> None:
        """Fourth column must show the direction (in/out)."""
        view = _make_view(qapp, items=_SAMPLE_PAYMENTS)
        assert view._model.item(0, 3).text() == "in"
        assert view._model.item(1, 3).text() == "out"

    def test_row_data_amount_column(self, qapp) -> None:
        """Fifth column must show the amount."""
        view = _make_view(qapp, items=_SAMPLE_PAYMENTS)
        assert view._model.item(0, 4).text() == "1500.00"

    def test_row_data_method_column(self, qapp) -> None:
        """Sixth column must show the payment method."""
        view = _make_view(qapp, items=_SAMPLE_PAYMENTS)
        assert view._model.item(0, 5).text() == "bank_transfer"

    def test_row_data_status_column(self, qapp) -> None:
        """Seventh column must show the status."""
        view = _make_view(qapp, items=_SAMPLE_PAYMENTS)
        assert view._model.item(0, 6).text() == "cleared"
        assert view._model.item(2, 6).text() == "pending"

    def test_amount_right_aligned(self, qapp) -> None:
        """Amount column items must be right-aligned."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_PAYMENTS)
        item = view._model.item(0, 4)
        assert item.textAlignment() & Qt.AlignmentFlag.AlignRight

    def test_payment_id_stored_as_user_role(self, qapp) -> None:
        """The payment id must be stored as UserRole on the date column item."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_PAYMENTS)
        stored_id = view._model.item(0, 0).data(Qt.ItemDataRole.UserRole)
        assert stored_id == "pmt-001"

    def test_empty_state_zero_rows(self, qapp) -> None:
        """When service returns empty list, model must have 0 rows."""
        view = _make_view(qapp, items=[])
        assert view._model.rowCount() == 0

    def test_contact_fallback_field(self, qapp) -> None:
        """Contact column must fall back to 'contact' key if 'contact_name' is absent."""
        pmt = {
            "id": "pmt-fb",
            "date": "2024-01-01",
            "reference": "REF-FB",
            "contact": "Fallback Contact",
            "direction": "out",
            "amount": "50.00",
            "method": "cash",
            "status": "cleared",
        }
        view = _make_view(qapp, items=[pmt])
        assert view._model.item(0, 2).text() == "Fallback Contact"


class TestPaymentsViewOffline:
    def test_offline_banner_shown_on_server_error(self, qapp) -> None:
        """Offline banner must be visible when service raises ServerOfflineError."""
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _make_view(qapp, side_effect=ServerOfflineError("offline"))
        assert not view._offline_label.isHidden()

    def test_offline_banner_hidden_when_data_loads(self, qapp) -> None:
        """Offline banner must be hidden when data loads successfully."""
        view = _make_view(qapp, items=_SAMPLE_PAYMENTS)
        assert view._offline_label.isHidden()


class TestPaymentsViewFilterToolbar:
    def test_has_direction_combo(self, qapp) -> None:
        """View must expose a direction filter QComboBox."""
        from PySide6.QtWidgets import QComboBox

        view = _make_view(qapp, items=[])
        assert isinstance(view._direction_combo, QComboBox)

    def test_direction_combo_options(self, qapp) -> None:
        """Direction combo must contain All, In, Out."""
        view = _make_view(qapp, items=[])
        options = [
            view._direction_combo.itemText(i)
            for i in range(view._direction_combo.count())
        ]
        assert options == ["All", "In", "Out"]

    def test_has_new_payment_button(self, qapp) -> None:
        """View must expose a New Payment QPushButton."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._new_btn, QPushButton)
        assert view._new_btn.text() == "New Payment"

    def test_direction_filter_triggers_reload(self, qapp) -> None:
        """Changing the direction combo must trigger a fresh load (page reset to 1)."""
        from PySide6.QtWidgets import QApplication

        call_count = 0

        def _side_effect(client, page=1, page_size=50, **kwargs):
            nonlocal call_count
            call_count += 1
            return []

        with patch(
            "saebooks_desktop.views.payments.list_payments",
            side_effect=_side_effect,
        ):
            from saebooks_desktop.views.payments import PaymentsView

            view = PaymentsView()
            before = call_count
            view._direction_combo.setCurrentIndex(1)  # select "In"
            QApplication.processEvents()
            assert call_count > before, "list_payments should have been called again"


class TestPaymentsViewDoubleClick:
    def test_double_click_emits_payment_selected(self, qapp) -> None:
        """Double-clicking a row must emit payment_selected with the payment id."""
        view = _make_view(qapp, items=_SAMPLE_PAYMENTS)

        received: list[str] = []
        view.payment_selected.connect(received.append)

        index = view._model.index(0, 0)
        view._on_double_click(index)

        assert received == ["pmt-001"]

    def test_double_click_second_row(self, qapp) -> None:
        """Double-clicking row 1 must emit the id of the second payment."""
        view = _make_view(qapp, items=_SAMPLE_PAYMENTS)

        received: list[str] = []
        view.payment_selected.connect(received.append)

        index = view._model.index(1, 0)
        view._on_double_click(index)

        assert received == ["pmt-002"]

    def test_new_payment_signal_emitted(self, qapp) -> None:
        """Clicking New Payment must emit new_payment_requested."""
        view = _make_view(qapp, items=[])

        triggered = []
        view.new_payment_requested.connect(lambda: triggered.append(True))
        view._new_btn.click()

        assert triggered == [True]


class TestPaymentsViewPagination:
    def test_load_more_button_exists(self, qapp) -> None:
        """View must expose a Load more QPushButton."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._load_more_btn, QPushButton)

    def test_load_more_disabled_when_fewer_than_page_size(self, qapp) -> None:
        """Load more must be disabled when fewer than 50 items are returned."""
        view = _make_view(qapp, items=_SAMPLE_PAYMENTS)  # only 3 items
        assert not view._load_more_btn.isEnabled()

    def test_load_more_appends_rows(self, qapp) -> None:
        """Clicking Load more must append the next page to the existing rows."""
        _PAGE_SIZE = 50
        page_1 = (_SAMPLE_PAYMENTS * 20)[:_PAGE_SIZE]  # exactly 50 items

        extra_payment = {
            "id": "pmt-extra",
            "date": "2024-02-01",
            "reference": "PMT-EXTRA",
            "contact_name": "Delta Ltd",
            "direction": "in",
            "amount": "200.00",
            "method": "cash",
            "status": "cleared",
        }

        with patch(
            "saebooks_desktop.views.payments.list_payments", return_value=page_1
        ):
            from saebooks_desktop.views.payments import PaymentsView

            view = PaymentsView()

        rows_after_first_load = view._model.rowCount()
        assert rows_after_first_load == _PAGE_SIZE

        with patch(
            "saebooks_desktop.views.payments.list_payments",
            return_value=[extra_payment],
        ):
            view._on_load_more()

        assert view._model.rowCount() == rows_after_first_load + 1
        assert view._model.item(rows_after_first_load, 1).text() == "PMT-EXTRA"
