"""Tests for ItemsView — offscreen Qt, mocked API service layer.

All tests run without a real API server.  The service function
``saebooks_desktop.services.items.list_items`` is patched at the
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

_SAMPLE_ITEMS = [
    {
        "id": "itm-001",
        "code": "WIDGET-A",
        "name": "Widget A",
        "type": "inventory",
        "unit_price": "29.99",
        "cost_price": "12.00",
        "on_hand": 100,
    },
    {
        "id": "itm-002",
        "code": "SVC-CONSULT",
        "name": "Consulting Hour",
        "type": "service",
        "unit_price": "150.00",
        "cost_price": "0.00",
        "on_hand": 0,
    },
    {
        "id": "itm-003",
        "code": "MISC-001",
        "name": "Misc Part",
        "type": "noninventory",
        "unit_price": "5.50",
        "cost_price": "2.25",
        "on_hand": 0,
    },
]

_PATCH_TARGET = "saebooks_desktop.views.items_view.list_items"


# ---------------------------------------------------------------------------
# Helper to build a view with a mocked list_items
# ---------------------------------------------------------------------------


def _make_view(qapp, items=None, side_effect=None):
    """Create ItemsView with list_items patched to return *items*."""
    from saebooks_desktop.views.items_view import ItemsView

    if side_effect is not None:
        with patch(_PATCH_TARGET, side_effect=side_effect):
            return ItemsView()
    else:
        with patch(_PATCH_TARGET, return_value=items if items is not None else []):
            return ItemsView()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestItemsViewInstantiation:
    def test_instantiates_without_crash(self, qapp) -> None:
        """ItemsView must create without raising when API is mocked."""
        view = _make_view(qapp, items=[])
        assert view is not None

    def test_has_table_model(self, qapp) -> None:
        """View must expose a QStandardItemModel on _model."""
        from PySide6.QtGui import QStandardItemModel

        view = _make_view(qapp, items=[])
        assert isinstance(view._model, QStandardItemModel)

    def test_has_six_columns(self, qapp) -> None:
        """Model must have 6 columns: Code, Name, Type, Unit Price, Cost Price, On Hand."""
        view = _make_view(qapp, items=[])
        assert view._model.columnCount() == 6

    def test_column_headers(self, qapp) -> None:
        """Column headers must match the spec exactly."""
        expected = ["Code", "Name", "Type", "Unit Price", "Cost Price", "On Hand"]
        view = _make_view(qapp, items=[])
        headers = [
            view._model.horizontalHeaderItem(i).text()
            for i in range(view._model.columnCount())
        ]
        assert headers == expected


class TestItemsViewModelPopulation:
    def test_row_count_matches_items(self, qapp) -> None:
        """Model must have one row per item returned by the service."""
        view = _make_view(qapp, items=_SAMPLE_ITEMS)
        assert view._model.rowCount() == 3

    def test_row_data_code_column(self, qapp) -> None:
        """First column must show the item code."""
        view = _make_view(qapp, items=_SAMPLE_ITEMS)
        assert view._model.item(0, 0).text() == "WIDGET-A"
        assert view._model.item(1, 0).text() == "SVC-CONSULT"

    def test_row_data_name_column(self, qapp) -> None:
        """Second column must show the item name."""
        view = _make_view(qapp, items=_SAMPLE_ITEMS)
        assert view._model.item(0, 1).text() == "Widget A"

    def test_row_data_type_column(self, qapp) -> None:
        """Third column must show the item type."""
        view = _make_view(qapp, items=_SAMPLE_ITEMS)
        assert view._model.item(0, 2).text() == "inventory"
        assert view._model.item(1, 2).text() == "service"
        assert view._model.item(2, 2).text() == "noninventory"

    def test_unit_price_right_aligned(self, qapp) -> None:
        """Unit Price column items must be right-aligned."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_ITEMS)
        item = view._model.item(0, 3)
        alignment = item.textAlignment()
        assert alignment & Qt.AlignmentFlag.AlignRight

    def test_cost_price_right_aligned(self, qapp) -> None:
        """Cost Price column items must be right-aligned."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_ITEMS)
        item = view._model.item(0, 4)
        alignment = item.textAlignment()
        assert alignment & Qt.AlignmentFlag.AlignRight

    def test_on_hand_right_aligned(self, qapp) -> None:
        """On Hand column items must be right-aligned."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_ITEMS)
        item = view._model.item(0, 5)
        alignment = item.textAlignment()
        assert alignment & Qt.AlignmentFlag.AlignRight

    def test_on_hand_integer_display(self, qapp) -> None:
        """On Hand column must display integer value."""
        view = _make_view(qapp, items=_SAMPLE_ITEMS)
        assert view._model.item(0, 5).text() == "100"
        assert view._model.item(1, 5).text() == "0"

    def test_item_id_stored_as_user_role(self, qapp) -> None:
        """The item id must be stored as UserRole on the code column item."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_ITEMS)
        stored_id = view._model.item(0, 0).data(Qt.ItemDataRole.UserRole)
        assert stored_id == "itm-001"

    def test_empty_state_zero_rows(self, qapp) -> None:
        """When service returns empty list, model must have 0 rows."""
        view = _make_view(qapp, items=[])
        assert view._model.rowCount() == 0


class TestItemsViewOffline:
    def test_offline_banner_shown_on_server_error(self, qapp) -> None:
        """Offline banner must be visible when service raises ServerOfflineError."""
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _make_view(qapp, side_effect=ServerOfflineError("offline"))
        assert not view._offline_label.isHidden()

    def test_offline_banner_hidden_when_data_loads(self, qapp) -> None:
        """Offline banner must be hidden when data loads successfully."""
        view = _make_view(qapp, items=_SAMPLE_ITEMS)
        assert view._offline_label.isHidden()


class TestItemsViewFilterToolbar:
    def test_has_type_combo(self, qapp) -> None:
        """View must expose a type filter QComboBox."""
        from PySide6.QtWidgets import QComboBox

        view = _make_view(qapp, items=[])
        assert isinstance(view._type_combo, QComboBox)

    def test_type_combo_options(self, qapp) -> None:
        """Type combo must contain All, Inventory, Service, NonInventory."""
        view = _make_view(qapp, items=[])
        options = [
            view._type_combo.itemText(i)
            for i in range(view._type_combo.count())
        ]
        assert options == ["All", "Inventory", "Service", "NonInventory"]

    def test_has_search_edit(self, qapp) -> None:
        """View must expose a search QLineEdit."""
        from PySide6.QtWidgets import QLineEdit

        view = _make_view(qapp, items=[])
        assert isinstance(view._search_edit, QLineEdit)

    def test_has_new_item_button(self, qapp) -> None:
        """View must expose a New Item QPushButton."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._new_btn, QPushButton)
        assert view._new_btn.text() == "New Item"

    def test_has_export_csv_button(self, qapp) -> None:
        """View must expose an Export CSV QPushButton."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._export_btn, QPushButton)
        assert view._export_btn.text() == "Export CSV"

    def test_type_filter_triggers_reload(self, qapp) -> None:
        """Changing the type combo must trigger a fresh load (page reset to 1)."""
        from PySide6.QtWidgets import QApplication

        call_count = 0

        def _side_effect(client, page=1, page_size=50, **kwargs):
            nonlocal call_count
            call_count += 1
            return []

        with patch(_PATCH_TARGET, side_effect=_side_effect):
            from saebooks_desktop.views.items_view import ItemsView

            view = ItemsView()
            before = call_count
            view._type_combo.setCurrentIndex(1)  # select "Inventory"
            QApplication.processEvents()
            assert call_count > before, "list_items should have been called again"


class TestItemsViewDoubleClick:
    def test_double_click_emits_item_selected(self, qapp) -> None:
        """Double-clicking a row must emit item_selected with the item id."""
        view = _make_view(qapp, items=_SAMPLE_ITEMS)

        received: list[str] = []
        view.item_selected.connect(received.append)

        index = view._model.index(0, 0)
        view._on_double_click(index)

        assert received == ["itm-001"]

    def test_double_click_second_row(self, qapp) -> None:
        """Double-clicking row 1 must emit the id of the second item."""
        view = _make_view(qapp, items=_SAMPLE_ITEMS)

        received: list[str] = []
        view.item_selected.connect(received.append)

        index = view._model.index(1, 0)
        view._on_double_click(index)

        assert received == ["itm-002"]

    def test_new_item_signal_emitted(self, qapp) -> None:
        """Clicking New Item must emit new_item_requested."""
        view = _make_view(qapp, items=[])

        triggered = []
        view.new_item_requested.connect(lambda: triggered.append(True))
        view._new_btn.click()

        assert triggered == [True]


class TestItemsViewPagination:
    def test_load_more_button_exists(self, qapp) -> None:
        """View must expose a Load more QPushButton."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._load_more_btn, QPushButton)

    def test_load_more_disabled_when_fewer_than_page_size(self, qapp) -> None:
        """Load more must be disabled when fewer than 50 items are returned."""
        view = _make_view(qapp, items=_SAMPLE_ITEMS)  # only 3 items
        assert not view._load_more_btn.isEnabled()

    def test_load_more_appends_rows(self, qapp) -> None:
        """Clicking Load more must append the next page to the existing rows."""
        _PAGE_SIZE = 50
        page_1 = (_SAMPLE_ITEMS * 20)[:_PAGE_SIZE]  # exactly 50 items

        extra_item = {
            "id": "itm-extra",
            "code": "EXTRA-001",
            "name": "Extra Widget",
            "type": "inventory",
            "unit_price": "9.99",
            "cost_price": "4.00",
            "on_hand": 5,
        }

        with patch(_PATCH_TARGET, return_value=page_1):
            from saebooks_desktop.views.items_view import ItemsView

            view = ItemsView()

        rows_after_first_load = view._model.rowCount()
        assert rows_after_first_load == _PAGE_SIZE

        with patch(_PATCH_TARGET, return_value=[extra_item]):
            view._on_load_more()

        assert view._model.rowCount() == rows_after_first_load + 1
        assert view._model.item(rows_after_first_load, 0).text() == "EXTRA-001"
