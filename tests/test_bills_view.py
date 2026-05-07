"""Tests for BillsView — offscreen Qt, mocked API service layer.

All tests run without a real API server.  The service function
``saebooks_desktop.services.invoices.list_bills`` is patched at the
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

_SAMPLE_BILLS = [
    {
        "id": "bill-001",
        "number": "BILL-0001",
        "supplier_name": "Supplier A",
        "bill_date": "2024-01-10",
        "due_date": "2024-02-10",
        "amount": "500.00",
        "status": "posted",
    },
    {
        "id": "bill-002",
        "number": "BILL-0002",
        "supplier_name": "Supplier B",
        "bill_date": "2024-01-15",
        "due_date": "2024-02-15",
        "amount": "1200.00",
        "status": "draft",
    },
    {
        "id": "bill-003",
        "number": "BILL-0003",
        "supplier_name": "Supplier C",
        "bill_date": "2024-01-20",
        "due_date": "2024-02-20",
        "amount": "300.00",
        "status": "voided",
    },
]


# ---------------------------------------------------------------------------
# Helper to build a view with a mocked list_bills
# ---------------------------------------------------------------------------


def _make_view(qapp, items=None, side_effect=None):
    """Create BillsView with list_bills patched to return *items*."""
    from saebooks_desktop.views.bills import BillsView

    if side_effect is not None:
        with patch(
            "saebooks_desktop.views.bills.list_bills",
            side_effect=side_effect,
        ):
            return BillsView()
    else:
        with patch(
            "saebooks_desktop.views.bills.list_bills",
            return_value=items if items is not None else [],
        ):
            return BillsView()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBillsViewInstantiation:
    def test_instantiates_without_crash(self, qapp) -> None:
        """BillsView must create without raising when API is mocked."""
        view = _make_view(qapp, items=[])
        assert view is not None

    def test_has_table_model(self, qapp) -> None:
        """View must expose a QStandardItemModel on _model."""
        from PySide6.QtGui import QStandardItemModel

        view = _make_view(qapp, items=[])
        assert isinstance(view._model, QStandardItemModel)

    def test_has_six_columns(self, qapp) -> None:
        """Model must have 6 columns."""
        view = _make_view(qapp, items=[])
        assert view._model.columnCount() == 6

    def test_column_headers(self, qapp) -> None:
        """Column headers must match the AP spec."""
        expected = ["Number", "Supplier", "Bill Date", "Due Date", "Amount", "Status"]
        view = _make_view(qapp, items=[])
        headers = [
            view._model.horizontalHeaderItem(i).text()
            for i in range(view._model.columnCount())
        ]
        assert headers == expected


class TestBillsViewModelPopulation:
    def test_row_count_matches_items(self, qapp) -> None:
        """Model must have one row per bill returned by the service."""
        view = _make_view(qapp, items=_SAMPLE_BILLS)
        assert view._model.rowCount() == 3

    def test_row_data_number_column(self, qapp) -> None:
        """First column must show the bill number."""
        view = _make_view(qapp, items=_SAMPLE_BILLS)
        assert view._model.item(0, 0).text() == "BILL-0001"

    def test_row_data_supplier_column(self, qapp) -> None:
        """Second column must show the supplier name."""
        view = _make_view(qapp, items=_SAMPLE_BILLS)
        assert view._model.item(0, 1).text() == "Supplier A"
        assert view._model.item(1, 1).text() == "Supplier B"

    def test_row_data_status_column(self, qapp) -> None:
        """Sixth column must show the status string."""
        view = _make_view(qapp, items=_SAMPLE_BILLS)
        assert view._model.item(0, 5).text() == "posted"
        assert view._model.item(1, 5).text() == "draft"
        assert view._model.item(2, 5).text() == "voided"

    def test_amount_right_aligned(self, qapp) -> None:
        """Amount column items must be right-aligned."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_BILLS)
        amount_item = view._model.item(0, 4)
        alignment = amount_item.textAlignment()
        assert alignment & Qt.AlignmentFlag.AlignRight

    def test_bill_id_stored_as_user_role(self, qapp) -> None:
        """The bill id must be stored as UserRole on the number column item."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_BILLS)
        stored_id = view._model.item(0, 0).data(Qt.ItemDataRole.UserRole)
        assert stored_id == "bill-001"

    def test_empty_state_zero_rows(self, qapp) -> None:
        """When service returns empty list, model must have 0 rows."""
        view = _make_view(qapp, items=[])
        assert view._model.rowCount() == 0


class TestBillsViewOffline:
    def test_offline_banner_shown_on_server_error(self, qapp) -> None:
        """Offline banner must be visible when service raises ServerOfflineError."""
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _make_view(qapp, side_effect=ServerOfflineError("offline"))
        assert not view._offline_label.isHidden()

    def test_offline_banner_hidden_when_data_loads(self, qapp) -> None:
        """Offline banner must be hidden when data loads successfully."""
        view = _make_view(qapp, items=_SAMPLE_BILLS)
        assert view._offline_label.isHidden()


class TestBillsViewFilterToolbar:
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

    def test_has_new_bill_button(self, qapp) -> None:
        """View must expose a New Bill QPushButton."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._new_btn, QPushButton)
        assert view._new_btn.text() == "New Bill"

    def test_has_load_more_button(self, qapp) -> None:
        """View must expose a Load more button."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._load_more_btn, QPushButton)


class TestBillsViewDoubleClick:
    def test_double_click_emits_bill_selected(self, qapp) -> None:
        """Double-clicking a row must emit bill_selected with the bill id."""
        view = _make_view(qapp, items=_SAMPLE_BILLS)

        received: list[str] = []
        view.bill_selected.connect(received.append)

        index = view._model.index(0, 0)
        view._on_double_click(index)

        assert received == ["bill-001"]

    def test_double_click_second_row(self, qapp) -> None:
        """Double-clicking row 1 must emit the id of the second bill."""
        view = _make_view(qapp, items=_SAMPLE_BILLS)

        received: list[str] = []
        view.bill_selected.connect(received.append)

        index = view._model.index(1, 0)
        view._on_double_click(index)

        assert received == ["bill-002"]

    def test_new_bill_signal_emitted(self, qapp) -> None:
        """Clicking New Bill must emit new_bill_requested."""
        view = _make_view(qapp, items=[])

        triggered = []
        view.new_bill_requested.connect(lambda: triggered.append(True))
        view._new_btn.click()

        assert triggered == [True]


class TestBillsViewPagination:
    def test_load_more_disabled_when_fewer_than_page_size(self, qapp) -> None:
        """Load more must be disabled when fewer than page_size items are returned."""
        view = _make_view(qapp, items=_SAMPLE_BILLS)  # only 3 items
        assert not view._load_more_btn.isEnabled()

    def test_load_more_appends_rows(self, qapp) -> None:
        """Clicking Load more must append the next page to existing rows."""
        _PAGE_SIZE = 50
        page_1 = (_SAMPLE_BILLS * 20)[:_PAGE_SIZE]  # exactly 50 items

        extra_bill = {
            "id": "bill-extra",
            "number": "BILL-EXTRA",
            "supplier_name": "Supplier D",
            "bill_date": "2024-02-01",
            "due_date": "2024-03-01",
            "amount": "750.00",
            "status": "draft",
        }

        with patch(
            "saebooks_desktop.views.bills.list_bills", return_value=page_1
        ):
            from saebooks_desktop.views.bills import BillsView

            view = BillsView()

        rows_after_first_load = view._model.rowCount()
        assert rows_after_first_load == _PAGE_SIZE

        with patch(
            "saebooks_desktop.views.bills.list_bills",
            return_value=[extra_bill],
        ):
            view._on_load_more()

        assert view._model.rowCount() == rows_after_first_load + 1
        assert view._model.item(rows_after_first_load, 0).text() == "BILL-EXTRA"
