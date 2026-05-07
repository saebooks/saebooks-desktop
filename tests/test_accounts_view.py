"""Tests for AccountsView — offscreen Qt, mocked API service layer.

All tests run without a real API server.  The service function
``saebooks_desktop.services.accounts.list_accounts`` is patched at the
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

_SAMPLE_ACCOUNTS = [
    {
        "id": "acc-001",
        "code": "1000",
        "name": "Cash at Bank",
        "type": "Asset",
        "balance": "12500.00",
    },
    {
        "id": "acc-002",
        "code": "2000",
        "name": "Accounts Payable",
        "type": "Liability",
        "balance": "4300.00",
    },
    {
        "id": "acc-003",
        "code": "3000",
        "name": "Retained Earnings",
        "type": "Equity",
        "balance": "50000.00",
    },
    {
        "id": "acc-004",
        "code": "4000",
        "name": "Sales Revenue",
        "type": "Income",
        "balance": "95000.00",
    },
    {
        "id": "acc-005",
        "code": "5000",
        "name": "Cost of Goods Sold",
        "type": "Expense",
        "balance": "42000.00",
    },
]


# ---------------------------------------------------------------------------
# Helper to build a view with a mocked list_accounts
# ---------------------------------------------------------------------------


def _make_view(qapp, items=None, side_effect=None):
    """Create AccountsView with list_accounts patched to return *items*."""
    from saebooks_desktop.views.accounts import AccountsView

    if side_effect is not None:
        with patch(
            "saebooks_desktop.views.accounts.list_accounts",
            side_effect=side_effect,
        ):
            return AccountsView()
    else:
        with patch(
            "saebooks_desktop.views.accounts.list_accounts",
            return_value=items if items is not None else [],
        ):
            return AccountsView()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAccountsViewInstantiation:
    def test_instantiates_without_crash(self, qapp) -> None:
        """AccountsView must create without raising when API is mocked."""
        view = _make_view(qapp, items=[])
        assert view is not None

    def test_has_tree_model(self, qapp) -> None:
        """View must expose a QStandardItemModel on _model."""
        from PySide6.QtGui import QStandardItemModel

        view = _make_view(qapp, items=[])
        assert isinstance(view._model, QStandardItemModel)

    def test_has_four_columns(self, qapp) -> None:
        """Model must have 4 columns: Code, Name, Type, Balance."""
        view = _make_view(qapp, items=[])
        assert view._model.columnCount() == 4

    def test_column_headers(self, qapp) -> None:
        """Column headers must match the spec exactly."""
        expected = ["Code", "Name", "Type", "Balance"]
        view = _make_view(qapp, items=[])
        headers = [
            view._model.horizontalHeaderItem(i).text()
            for i in range(view._model.columnCount())
        ]
        assert headers == expected

    def test_uses_qtreeview(self, qapp) -> None:
        """View must use QTreeView as its primary widget."""
        from PySide6.QtWidgets import QTreeView

        view = _make_view(qapp, items=[])
        assert isinstance(view._tree, QTreeView)


class TestAccountsViewModelPopulation:
    def test_row_count_matches_items(self, qapp) -> None:
        """Model must have one row per account returned by the service."""
        view = _make_view(qapp, items=_SAMPLE_ACCOUNTS)
        assert view._model.rowCount() == 5

    def test_row_data_code_column(self, qapp) -> None:
        """First column must show the account code."""
        view = _make_view(qapp, items=_SAMPLE_ACCOUNTS)
        assert view._model.item(0, 0).text() == "1000"
        assert view._model.item(1, 0).text() == "2000"

    def test_row_data_name_column(self, qapp) -> None:
        """Second column must show the account name."""
        view = _make_view(qapp, items=_SAMPLE_ACCOUNTS)
        assert view._model.item(0, 1).text() == "Cash at Bank"

    def test_row_data_type_column(self, qapp) -> None:
        """Third column must show the account type."""
        view = _make_view(qapp, items=_SAMPLE_ACCOUNTS)
        assert view._model.item(0, 2).text() == "Asset"
        assert view._model.item(1, 2).text() == "Liability"

    def test_row_data_balance_column(self, qapp) -> None:
        """Fourth column must show the balance."""
        view = _make_view(qapp, items=_SAMPLE_ACCOUNTS)
        assert view._model.item(0, 3).text() == "12500.00"

    def test_balance_right_aligned(self, qapp) -> None:
        """Balance column items must be right-aligned."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_ACCOUNTS)
        balance_item = view._model.item(0, 3)
        alignment = balance_item.textAlignment()
        assert alignment & Qt.AlignmentFlag.AlignRight

    def test_account_id_stored_as_user_role(self, qapp) -> None:
        """The account id must be stored as UserRole on the code column item."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_ACCOUNTS)
        stored_id = view._model.item(0, 0).data(Qt.ItemDataRole.UserRole)
        assert stored_id == "acc-001"

    def test_empty_state_zero_rows(self, qapp) -> None:
        """When service returns empty list, model must have 0 rows."""
        view = _make_view(qapp, items=[])
        assert view._model.rowCount() == 0


class TestAccountsViewOffline:
    def test_offline_banner_shown_on_server_error(self, qapp) -> None:
        """Offline banner must be visible when service raises ServerOfflineError."""
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _make_view(qapp, side_effect=ServerOfflineError("offline"))
        assert not view._offline_label.isHidden()

    def test_offline_banner_hidden_when_data_loads(self, qapp) -> None:
        """Offline banner must be hidden when data loads successfully."""
        view = _make_view(qapp, items=_SAMPLE_ACCOUNTS)
        assert view._offline_label.isHidden()


class TestAccountsViewFilterToolbar:
    def test_has_search_box(self, qapp) -> None:
        """View must expose a QLineEdit search box."""
        from PySide6.QtWidgets import QLineEdit

        view = _make_view(qapp, items=[])
        assert isinstance(view._search_box, QLineEdit)

    def test_has_type_combo(self, qapp) -> None:
        """View must expose a type filter QComboBox."""
        from PySide6.QtWidgets import QComboBox

        view = _make_view(qapp, items=[])
        assert isinstance(view._type_combo, QComboBox)

    def test_type_combo_options(self, qapp) -> None:
        """Type combo must contain All, Asset, Liability, Equity, Income, Expense."""
        view = _make_view(qapp, items=[])
        options = [
            view._type_combo.itemText(i)
            for i in range(view._type_combo.count())
        ]
        assert options == ["All", "Asset", "Liability", "Equity", "Income", "Expense"]

    def test_has_new_account_button(self, qapp) -> None:
        """View must expose a New Account QPushButton."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._new_btn, QPushButton)
        assert view._new_btn.text() == "New Account"

    def test_type_filter_applies(self, qapp) -> None:
        """Selecting a type filter must reduce rows to matching type only."""
        from PySide6.QtWidgets import QApplication

        view = _make_view(qapp, items=_SAMPLE_ACCOUNTS)
        # All 5 accounts visible initially
        assert view._model.rowCount() == 5

        # Select "Asset" — only acc-001 qualifies
        view._type_combo.setCurrentText("Asset")
        QApplication.processEvents()
        assert view._model.rowCount() == 1
        assert view._model.item(0, 0).text() == "1000"

    def test_search_filter_by_code(self, qapp) -> None:
        """Typing in the search box must filter rows by code."""
        from PySide6.QtWidgets import QApplication

        view = _make_view(qapp, items=_SAMPLE_ACCOUNTS)
        view._search_box.setText("3000")
        QApplication.processEvents()
        assert view._model.rowCount() == 1
        assert view._model.item(0, 1).text() == "Retained Earnings"

    def test_search_filter_by_name(self, qapp) -> None:
        """Typing in the search box must filter rows by name."""
        from PySide6.QtWidgets import QApplication

        view = _make_view(qapp, items=_SAMPLE_ACCOUNTS)
        view._search_box.setText("payable")
        QApplication.processEvents()
        assert view._model.rowCount() == 1
        assert view._model.item(0, 0).text() == "2000"

    def test_search_filter_no_match_gives_zero_rows(self, qapp) -> None:
        """Search with no matching accounts must yield 0 rows."""
        from PySide6.QtWidgets import QApplication

        view = _make_view(qapp, items=_SAMPLE_ACCOUNTS)
        view._search_box.setText("ZZZNOMATCH")
        QApplication.processEvents()
        assert view._model.rowCount() == 0


class TestAccountsViewDoubleClick:
    def test_double_click_emits_account_selected(self, qapp) -> None:
        """Double-clicking a row must emit account_selected with the account id."""
        view = _make_view(qapp, items=_SAMPLE_ACCOUNTS)

        received: list[str] = []
        view.account_selected.connect(received.append)

        index = view._model.index(0, 0)
        view._on_double_click(index)

        assert received == ["acc-001"]

    def test_double_click_second_row(self, qapp) -> None:
        """Double-clicking row 1 must emit the id of the second account."""
        view = _make_view(qapp, items=_SAMPLE_ACCOUNTS)

        received: list[str] = []
        view.account_selected.connect(received.append)

        index = view._model.index(1, 0)
        view._on_double_click(index)

        assert received == ["acc-002"]

    def test_new_account_signal_emitted(self, qapp) -> None:
        """Clicking New Account must emit new_account_requested."""
        view = _make_view(qapp, items=[])

        triggered = []
        view.new_account_requested.connect(lambda: triggered.append(True))
        view._new_btn.click()

        assert triggered == [True]
