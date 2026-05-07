"""Tests for BudgetsView and BudgetDialog — offscreen Qt, mocked API service layer.

All tests run without a real API server.  The service functions
``saebooks_desktop.services.budgets.list_budgets`` and
``saebooks_desktop.services.budgets.create_budget`` are patched at the
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

_SAMPLE_BUDGETS = [
    {
        "id": "bud-001",
        "name": "Operations 2024-25",
        "fiscal_year": "2024-25",
        "total_income": "100000.00",
        "total_expense": "80000.00",
        "status": "active",
    },
    {
        "id": "bud-002",
        "name": "Capital 2023-24",
        "fiscal_year": "2023-24",
        "total_income": "50000.00",
        "total_expense": "45000.00",
        "status": "closed",
    },
    {
        "id": "bud-003",
        "name": "Marketing 2024-25",
        "fiscal_year": "2024-25",
        "total_income": "20000.00",
        "total_expense": "18000.00",
        "status": "active",
    },
]

_PATCH_LIST = "saebooks_desktop.views.budgets.list_budgets"
_PATCH_CREATE = "saebooks_desktop.views.budgets.create_budget"


# ---------------------------------------------------------------------------
# Helper to build a view with mocked list_budgets
# ---------------------------------------------------------------------------


def _make_view(qapp, items=None, side_effect=None):
    """Create BudgetsView with list_budgets patched to return *items*."""
    from saebooks_desktop.views.budgets import BudgetsView

    if side_effect is not None:
        with patch(_PATCH_LIST, side_effect=side_effect):
            return BudgetsView()
    else:
        with patch(_PATCH_LIST, return_value=items if items is not None else []):
            return BudgetsView()


# ---------------------------------------------------------------------------
# Tests — Instantiation
# ---------------------------------------------------------------------------


class TestBudgetsViewInstantiation:
    def test_instantiates_without_crash(self, qapp) -> None:
        """BudgetsView must create without raising when API is mocked."""
        view = _make_view(qapp, items=[])
        assert view is not None

    def test_has_table_model(self, qapp) -> None:
        """View must expose a QStandardItemModel on _model."""
        from PySide6.QtGui import QStandardItemModel

        view = _make_view(qapp, items=[])
        assert isinstance(view._model, QStandardItemModel)

    def test_has_three_columns(self, qapp) -> None:
        """Model must have 3 columns: Name, Year, Status."""
        view = _make_view(qapp, items=[])
        assert view._model.columnCount() == 3

    def test_column_headers(self, qapp) -> None:
        """Column headers must match the spec exactly."""
        expected = ["Name", "Year", "Status"]
        view = _make_view(qapp, items=[])
        headers = [
            view._model.horizontalHeaderItem(i).text()
            for i in range(view._model.columnCount())
        ]
        assert headers == expected


# ---------------------------------------------------------------------------
# Tests — Model population
# ---------------------------------------------------------------------------


class TestBudgetsViewModelPopulation:
    def test_row_count_matches_budgets(self, qapp) -> None:
        """Model must have one row per budget returned by the service."""
        view = _make_view(qapp, items=_SAMPLE_BUDGETS)
        assert view._model.rowCount() == 3

    def test_row_data_name_column(self, qapp) -> None:
        """First column must show the budget name."""
        view = _make_view(qapp, items=_SAMPLE_BUDGETS)
        assert view._model.item(0, 0).text() == "Operations 2024-25"
        assert view._model.item(1, 0).text() == "Capital 2023-24"

    def test_row_data_year_column(self, qapp) -> None:
        """Second column must show the fiscal year."""
        view = _make_view(qapp, items=_SAMPLE_BUDGETS)
        assert view._model.item(0, 1).text() == "2024-25"
        assert view._model.item(1, 1).text() == "2023-24"

    def test_row_data_status_column(self, qapp) -> None:
        """Third column must show the status."""
        view = _make_view(qapp, items=_SAMPLE_BUDGETS)
        assert view._model.item(0, 2).text() == "active"
        assert view._model.item(1, 2).text() == "closed"

    def test_budget_id_stored_as_user_role(self, qapp) -> None:
        """The budget id must be stored as UserRole on the name column item."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_BUDGETS)
        stored_id = view._model.item(0, 0).data(Qt.ItemDataRole.UserRole)
        assert stored_id == "bud-001"

    def test_empty_state_zero_rows(self, qapp) -> None:
        """When service returns empty list, model must have 0 rows."""
        view = _make_view(qapp, items=[])
        assert view._model.rowCount() == 0


# ---------------------------------------------------------------------------
# Tests — Offline
# ---------------------------------------------------------------------------


class TestBudgetsViewOffline:
    def test_offline_banner_shown_on_server_error(self, qapp) -> None:
        """Offline banner must be visible when service raises ServerOfflineError."""
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _make_view(qapp, side_effect=ServerOfflineError("offline"))
        assert not view._offline_label.isHidden()

    def test_offline_banner_hidden_when_data_loads(self, qapp) -> None:
        """Offline banner must be hidden when data loads successfully."""
        view = _make_view(qapp, items=_SAMPLE_BUDGETS)
        assert view._offline_label.isHidden()


# ---------------------------------------------------------------------------
# Tests — Filter toolbar
# ---------------------------------------------------------------------------


class TestBudgetsViewFilterToolbar:
    def test_has_status_combo(self, qapp) -> None:
        """View must expose a status filter QComboBox."""
        from PySide6.QtWidgets import QComboBox

        view = _make_view(qapp, items=[])
        assert isinstance(view._status_combo, QComboBox)

    def test_status_combo_options(self, qapp) -> None:
        """Status combo must contain All, Active, Closed."""
        view = _make_view(qapp, items=[])
        options = [
            view._status_combo.itemText(i)
            for i in range(view._status_combo.count())
        ]
        assert options == ["All", "Active", "Closed"]

    def test_has_new_budget_button(self, qapp) -> None:
        """View must expose a New Budget QPushButton."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._new_btn, QPushButton)
        assert view._new_btn.text() == "New Budget"

    def test_status_filter_triggers_reload(self, qapp) -> None:
        """Changing the status combo must trigger a fresh load (page reset to 1)."""
        from PySide6.QtWidgets import QApplication

        call_count = 0

        def _side_effect(client, page=1, page_size=50, **kwargs):
            nonlocal call_count
            call_count += 1
            return []

        with patch(_PATCH_LIST, side_effect=_side_effect):
            from saebooks_desktop.views.budgets import BudgetsView

            view = BudgetsView()
            before = call_count
            view._status_combo.setCurrentIndex(1)  # select "Active"
            QApplication.processEvents()
            assert call_count > before, "list_budgets should have been called again"


# ---------------------------------------------------------------------------
# Tests — Double-click
# ---------------------------------------------------------------------------


class TestBudgetsViewDoubleClick:
    def test_double_click_emits_budget_selected(self, qapp) -> None:
        """Double-clicking a row must emit budget_selected with the budget id."""
        view = _make_view(qapp, items=_SAMPLE_BUDGETS)

        received: list[str] = []
        view.budget_selected.connect(received.append)

        index = view._model.index(0, 0)
        view._on_double_click(index)

        assert received == ["bud-001"]

    def test_double_click_second_row(self, qapp) -> None:
        """Double-clicking row 1 must emit the id of the second budget."""
        view = _make_view(qapp, items=_SAMPLE_BUDGETS)

        received: list[str] = []
        view.budget_selected.connect(received.append)

        index = view._model.index(1, 0)
        view._on_double_click(index)

        assert received == ["bud-002"]


# ---------------------------------------------------------------------------
# Tests — Pagination
# ---------------------------------------------------------------------------


class TestBudgetsViewPagination:
    def test_load_more_button_exists(self, qapp) -> None:
        """View must expose a Load more QPushButton."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._load_more_btn, QPushButton)

    def test_load_more_disabled_when_fewer_than_page_size(self, qapp) -> None:
        """Load more must be disabled when fewer than 50 items are returned."""
        view = _make_view(qapp, items=_SAMPLE_BUDGETS)  # only 3 items
        assert not view._load_more_btn.isEnabled()

    def test_load_more_appends_rows(self, qapp) -> None:
        """Clicking Load more must append the next page to the existing rows."""
        _PAGE_SIZE = 50
        page_1 = (_SAMPLE_BUDGETS * 20)[:_PAGE_SIZE]

        extra_budget = {
            "id": "bud-extra",
            "name": "Extra Budget",
            "fiscal_year": "2025-26",
            "status": "active",
        }

        with patch(_PATCH_LIST, return_value=page_1):
            from saebooks_desktop.views.budgets import BudgetsView

            view = BudgetsView()

        rows_after_first_load = view._model.rowCount()
        assert rows_after_first_load == _PAGE_SIZE

        with patch(_PATCH_LIST, return_value=[extra_budget]):
            view._on_load_more()

        assert view._model.rowCount() == rows_after_first_load + 1
        assert view._model.item(rows_after_first_load, 0).text() == "Extra Budget"


# ---------------------------------------------------------------------------
# Tests — BudgetDialog
# ---------------------------------------------------------------------------


class TestBudgetDialog:
    def test_dialog_instantiates(self, qapp) -> None:
        """BudgetDialog must instantiate without crashing."""
        from saebooks_desktop.views.budgets import BudgetDialog

        dlg = BudgetDialog()
        assert dlg is not None

    def test_dialog_has_name_field(self, qapp) -> None:
        """BudgetDialog must expose a _name_edit QLineEdit."""
        from PySide6.QtWidgets import QLineEdit

        from saebooks_desktop.views.budgets import BudgetDialog

        dlg = BudgetDialog()
        assert isinstance(dlg._name_edit, QLineEdit)

    def test_dialog_has_year_field(self, qapp) -> None:
        """BudgetDialog must expose a _year_edit QLineEdit."""
        from PySide6.QtWidgets import QLineEdit

        from saebooks_desktop.views.budgets import BudgetDialog

        dlg = BudgetDialog()
        assert isinstance(dlg._year_edit, QLineEdit)

    def test_name_accessor(self, qapp) -> None:
        """name() must return the text entered in _name_edit."""
        from saebooks_desktop.views.budgets import BudgetDialog

        dlg = BudgetDialog()
        dlg._name_edit.setText("  Operations 2024-25  ")
        assert dlg.name() == "Operations 2024-25"

    def test_fiscal_year_accessor(self, qapp) -> None:
        """fiscal_year() must return the text entered in _year_edit."""
        from saebooks_desktop.views.budgets import BudgetDialog

        dlg = BudgetDialog()
        dlg._year_edit.setText("  2024-25  ")
        assert dlg.fiscal_year() == "2024-25"
