"""Tests for BankingView — offscreen Qt, mocked API service layer.

All tests run without a real API server.  The service functions
``saebooks_desktop.services.banking.list_bank_statement_lines`` and
``saebooks_desktop.services.accounts.list_accounts`` are patched at their
import points inside the view so no HTTP calls are made.
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

_SAMPLE_BSLS = [
    {
        "id": "bsl-001",
        "date": "2024-01-10",
        "description": "Direct debit — rent",
        "reference": "REF-001",
        "debit": "2500.00",
        "credit": "",
        "balance": "12500.00",
        "status": "unmatched",
    },
    {
        "id": "bsl-002",
        "date": "2024-01-12",
        "description": "Customer payment",
        "reference": "REF-002",
        "debit": "",
        "credit": "1500.00",
        "balance": "14000.00",
        "status": "matched",
    },
    {
        "id": "bsl-003",
        "date": "2024-01-15",
        "description": "Bank fee",
        "reference": "REF-003",
        "debit": "15.00",
        "credit": "",
        "balance": "13985.00",
        "status": "ignored",
    },
]

_SAMPLE_ACCOUNTS = [
    {"id": "acct-001", "code": "1010", "name": "Business Cheque", "reconcile": True},
    {"id": "acct-002", "code": "1020", "name": "Savings", "is_bank_account": True},
    {"id": "acct-003", "code": "2010", "name": "Accounts Payable", "reconcile": False},
]


# ---------------------------------------------------------------------------
# Helper to build a view with mocked services
# ---------------------------------------------------------------------------


def _make_view(qapp, items=None, side_effect=None, accounts=None):
    """Create BankingView with list_bank_statement_lines and list_accounts patched."""
    from saebooks_desktop.views.banking import BankingView

    acct_return = accounts if accounts is not None else []

    if side_effect is not None:
        with patch(
            "saebooks_desktop.views.banking.list_accounts",
            return_value=acct_return,
        ), patch(
            "saebooks_desktop.views.banking.list_bank_statement_lines",
            side_effect=side_effect,
        ):
            return BankingView()
    else:
        with patch(
            "saebooks_desktop.views.banking.list_accounts",
            return_value=acct_return,
        ), patch(
            "saebooks_desktop.views.banking.list_bank_statement_lines",
            return_value=items if items is not None else [],
        ):
            return BankingView()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBankingViewInstantiation:
    def test_instantiates_without_crash(self, qapp) -> None:
        """BankingView must create without raising when API is mocked."""
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
            "Date", "Description", "Reference",
            "Debit", "Credit", "Balance", "Status",
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


class TestBankingViewModelPopulation:
    def test_row_count_matches_items(self, qapp) -> None:
        """Model must have one row per BSL returned by the service."""
        view = _make_view(qapp, items=_SAMPLE_BSLS)
        assert view._model.rowCount() == 3

    def test_row_data_date_column(self, qapp) -> None:
        """First column must show the BSL date."""
        view = _make_view(qapp, items=_SAMPLE_BSLS)
        assert view._model.item(0, 0).text() == "2024-01-10"
        assert view._model.item(1, 0).text() == "2024-01-12"

    def test_row_data_description_column(self, qapp) -> None:
        """Second column must show the description."""
        view = _make_view(qapp, items=_SAMPLE_BSLS)
        assert view._model.item(0, 1).text() == "Direct debit — rent"

    def test_row_data_reference_column(self, qapp) -> None:
        """Third column must show the reference."""
        view = _make_view(qapp, items=_SAMPLE_BSLS)
        assert view._model.item(0, 2).text() == "REF-001"

    def test_row_data_debit_column(self, qapp) -> None:
        """Fourth column must show the debit amount."""
        view = _make_view(qapp, items=_SAMPLE_BSLS)
        assert view._model.item(0, 3).text() == "2500.00"

    def test_row_data_credit_column(self, qapp) -> None:
        """Fifth column must show the credit amount."""
        view = _make_view(qapp, items=_SAMPLE_BSLS)
        assert view._model.item(1, 4).text() == "1500.00"

    def test_row_data_status_column(self, qapp) -> None:
        """Seventh column must show the status string."""
        view = _make_view(qapp, items=_SAMPLE_BSLS)
        assert view._model.item(0, 6).text() == "unmatched"
        assert view._model.item(1, 6).text() == "matched"
        assert view._model.item(2, 6).text() == "ignored"

    def test_debit_right_aligned(self, qapp) -> None:
        """Debit column items must be right-aligned."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_BSLS)
        item = view._model.item(0, 3)
        assert item.textAlignment() & Qt.AlignmentFlag.AlignRight

    def test_credit_right_aligned(self, qapp) -> None:
        """Credit column items must be right-aligned."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_BSLS)
        item = view._model.item(1, 4)
        assert item.textAlignment() & Qt.AlignmentFlag.AlignRight

    def test_balance_right_aligned(self, qapp) -> None:
        """Balance column items must be right-aligned."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_BSLS)
        item = view._model.item(0, 5)
        assert item.textAlignment() & Qt.AlignmentFlag.AlignRight

    def test_bsl_id_stored_as_user_role(self, qapp) -> None:
        """The BSL id must be stored as UserRole on the date column item."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_BSLS)
        stored_id = view._model.item(0, 0).data(Qt.ItemDataRole.UserRole)
        assert stored_id == "bsl-001"

    def test_empty_state_zero_rows(self, qapp) -> None:
        """When service returns empty list, model must have 0 rows."""
        view = _make_view(qapp, items=[])
        assert view._model.rowCount() == 0


class TestBankingViewOffline:
    def test_offline_banner_shown_on_server_error(self, qapp) -> None:
        """Offline banner must be visible when service raises ServerOfflineError."""
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _make_view(qapp, side_effect=ServerOfflineError("offline"))
        assert not view._offline_label.isHidden()

    def test_offline_banner_hidden_when_data_loads(self, qapp) -> None:
        """Offline banner must be hidden when data loads successfully."""
        view = _make_view(qapp, items=_SAMPLE_BSLS)
        assert view._offline_label.isHidden()


class TestBankingViewFilterToolbar:
    def test_has_account_combo(self, qapp) -> None:
        """View must expose an account filter QComboBox."""
        from PySide6.QtWidgets import QComboBox

        view = _make_view(qapp, items=[])
        assert isinstance(view._account_combo, QComboBox)

    def test_account_combo_default_entry(self, qapp) -> None:
        """Account combo must have 'All accounts' as its first entry."""
        view = _make_view(qapp, items=[])
        assert view._account_combo.itemText(0) == "All accounts"

    def test_account_combo_populated_from_reconcilable_accounts(self, qapp) -> None:
        """Account combo must include accounts with reconcile=True or is_bank_account=True."""
        view = _make_view(qapp, items=[], accounts=_SAMPLE_ACCOUNTS)
        # 'All accounts' + 2 reconcilable accounts (acct-001 and acct-002)
        assert view._account_combo.count() == 3

    def test_has_status_combo(self, qapp) -> None:
        """View must expose a status filter QComboBox."""
        from PySide6.QtWidgets import QComboBox

        view = _make_view(qapp, items=[])
        assert isinstance(view._status_combo, QComboBox)

    def test_status_combo_options(self, qapp) -> None:
        """Status combo must contain All, Unmatched, Matched."""
        view = _make_view(qapp, items=[])
        options = [
            view._status_combo.itemText(i)
            for i in range(view._status_combo.count())
        ]
        assert options == ["All", "Unmatched", "Matched"]

    def test_has_import_button(self, qapp) -> None:
        """View must expose an Import Statement QPushButton."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._import_btn, QPushButton)
        assert view._import_btn.text() == "Import Statement"

    def test_has_reconcile_button(self, qapp) -> None:
        """View must expose a Reconcile QPushButton."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._reconcile_btn, QPushButton)
        assert view._reconcile_btn.text() == "Reconcile"

    def test_status_filter_triggers_reload(self, qapp) -> None:
        """Changing the status combo must trigger a fresh load (page reset to 1)."""
        from PySide6.QtWidgets import QApplication

        call_count = 0

        def _bsl_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return []

        with patch(
            "saebooks_desktop.views.banking.list_accounts",
            return_value=[],
        ), patch(
            "saebooks_desktop.views.banking.list_bank_statement_lines",
            side_effect=_bsl_side_effect,
        ):
            from saebooks_desktop.views.banking import BankingView

            view = BankingView()
            before = call_count
            view._status_combo.setCurrentIndex(1)  # select "Unmatched"
            QApplication.processEvents()
            assert call_count > before, "list_bank_statement_lines should have been called again"


class TestBankingViewSignals:
    def test_double_click_emits_bsl_selected(self, qapp) -> None:
        """Double-clicking a row must emit bsl_selected with the BSL id."""
        view = _make_view(qapp, items=_SAMPLE_BSLS)

        received: list[str] = []
        view.bsl_selected.connect(received.append)

        index = view._model.index(0, 0)
        view._on_double_click(index)

        assert received == ["bsl-001"]

    def test_double_click_second_row(self, qapp) -> None:
        """Double-clicking row 1 must emit the id of the second BSL."""
        view = _make_view(qapp, items=_SAMPLE_BSLS)

        received: list[str] = []
        view.bsl_selected.connect(received.append)

        index = view._model.index(1, 0)
        view._on_double_click(index)

        assert received == ["bsl-002"]

    def test_import_button_emits_import_requested(self, qapp) -> None:
        """Clicking Import Statement must emit import_requested."""
        view = _make_view(qapp, items=[])

        triggered = []
        view.import_requested.connect(lambda: triggered.append(True))
        view._import_btn.click()

        assert triggered == [True]

    def test_reconcile_button_emits_reconcile_requested(self, qapp) -> None:
        """Clicking Reconcile must emit reconcile_requested."""
        view = _make_view(qapp, items=[])

        received: list[str] = []
        view.reconcile_requested.connect(received.append)
        view._reconcile_btn.click()

        assert len(received) == 1


class TestBankingViewPagination:
    def test_load_more_button_exists(self, qapp) -> None:
        """View must expose a Load more QPushButton."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._load_more_btn, QPushButton)

    def test_load_more_disabled_when_fewer_than_page_size(self, qapp) -> None:
        """Load more must be disabled when fewer than 50 items are returned."""
        view = _make_view(qapp, items=_SAMPLE_BSLS)  # only 3 items
        assert not view._load_more_btn.isEnabled()

    def test_load_more_appends_rows(self, qapp) -> None:
        """Clicking Load more must append the next page to the existing rows."""
        _PAGE_SIZE = 50
        page_1 = (_SAMPLE_BSLS * 20)[:_PAGE_SIZE]  # exactly 50 items

        extra_bsl = {
            "id": "bsl-extra",
            "date": "2024-02-01",
            "description": "Extra line",
            "reference": "REF-EXTRA",
            "debit": "100.00",
            "credit": "",
            "balance": "13885.00",
            "status": "unmatched",
        }

        with patch(
            "saebooks_desktop.views.banking.list_accounts",
            return_value=[],
        ), patch(
            "saebooks_desktop.views.banking.list_bank_statement_lines",
            return_value=page_1,
        ):
            from saebooks_desktop.views.banking import BankingView

            view = BankingView()

        rows_after_first_load = view._model.rowCount()
        assert rows_after_first_load == _PAGE_SIZE

        with patch(
            "saebooks_desktop.views.banking.list_bank_statement_lines",
            return_value=[extra_bsl],
        ):
            view._on_load_more()

        assert view._model.rowCount() == rows_after_first_load + 1
        assert view._model.item(rows_after_first_load, 1).text() == "Extra line"
