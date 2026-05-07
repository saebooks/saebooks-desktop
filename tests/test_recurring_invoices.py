"""Tests for RecurringInvoicesView — offscreen Qt, mocked API service layer.

All tests run without a real API server.  The service functions
``saebooks_desktop.services.recurring_invoices.list_recurring_invoices`` and
``saebooks_desktop.services.recurring_invoices.run_recurring_invoice`` are
patched at the module-level import point inside the view so no HTTP calls
are made.
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

_SAMPLE_RECURRING = [
    {
        "id": "ri-001",
        "name": "Monthly Retainer",
        "contact_id": "con-001",
        "contact_name": "Acme Corp",
        "frequency": "monthly",
        "next_date": "2024-02-01",
        "status": "active",
    },
    {
        "id": "ri-002",
        "name": "Weekly Maintenance",
        "contact_id": "con-002",
        "contact_name": "Beta Ltd",
        "frequency": "weekly",
        "next_date": "2024-01-22",
        "status": "active",
    },
    {
        "id": "ri-003",
        "name": "Annual Licence",
        "contact_id": "con-003",
        "contact_name": "Gamma Co",
        "frequency": "annually",
        "next_date": "2025-01-01",
        "status": "paused",
    },
]

_PATCH_LIST = "saebooks_desktop.views.recurring_invoices.list_recurring_invoices"
_PATCH_RUN = "saebooks_desktop.views.recurring_invoices.run_recurring_invoice"


# ---------------------------------------------------------------------------
# Helper to build a view with mocked list_recurring_invoices
# ---------------------------------------------------------------------------


def _make_view(qapp, items=None, side_effect=None):
    """Create RecurringInvoicesView with list_recurring_invoices patched."""
    from saebooks_desktop.views.recurring_invoices import RecurringInvoicesView

    if side_effect is not None:
        with patch(_PATCH_LIST, side_effect=side_effect):
            return RecurringInvoicesView()
    else:
        with patch(
            _PATCH_LIST, return_value=items if items is not None else []
        ):
            return RecurringInvoicesView()


# ---------------------------------------------------------------------------
# Tests — Instantiation
# ---------------------------------------------------------------------------


class TestRecurringInvoicesViewInstantiation:
    def test_instantiates_without_crash(self, qapp) -> None:
        """RecurringInvoicesView must create without raising when API is mocked."""
        view = _make_view(qapp, items=[])
        assert view is not None

    def test_has_table_model(self, qapp) -> None:
        """View must expose a QStandardItemModel on _model."""
        from PySide6.QtGui import QStandardItemModel

        view = _make_view(qapp, items=[])
        assert isinstance(view._model, QStandardItemModel)

    def test_has_five_columns(self, qapp) -> None:
        """Model must have 5 columns: Name, Contact, Frequency, Next Date, Status."""
        view = _make_view(qapp, items=[])
        assert view._model.columnCount() == 5

    def test_column_headers(self, qapp) -> None:
        """Column headers must match the spec exactly."""
        expected = ["Name", "Contact", "Frequency", "Next Date", "Status"]
        view = _make_view(qapp, items=[])
        headers = [
            view._model.horizontalHeaderItem(i).text()
            for i in range(view._model.columnCount())
        ]
        assert headers == expected


# ---------------------------------------------------------------------------
# Tests — Model population
# ---------------------------------------------------------------------------


class TestRecurringInvoicesViewModelPopulation:
    def test_row_count_matches_items(self, qapp) -> None:
        """Model must have one row per recurring invoice returned by the service."""
        view = _make_view(qapp, items=_SAMPLE_RECURRING)
        assert view._model.rowCount() == 3

    def test_row_data_name_column(self, qapp) -> None:
        """First column must show the recurring invoice name."""
        view = _make_view(qapp, items=_SAMPLE_RECURRING)
        assert view._model.item(0, 0).text() == "Monthly Retainer"
        assert view._model.item(1, 0).text() == "Weekly Maintenance"

    def test_row_data_contact_column(self, qapp) -> None:
        """Second column must show the contact name."""
        view = _make_view(qapp, items=_SAMPLE_RECURRING)
        assert view._model.item(0, 1).text() == "Acme Corp"
        assert view._model.item(1, 1).text() == "Beta Ltd"

    def test_row_data_frequency_column(self, qapp) -> None:
        """Third column must show the frequency."""
        view = _make_view(qapp, items=_SAMPLE_RECURRING)
        assert view._model.item(0, 2).text() == "monthly"
        assert view._model.item(1, 2).text() == "weekly"

    def test_row_data_next_date_column(self, qapp) -> None:
        """Fourth column must show the next date."""
        view = _make_view(qapp, items=_SAMPLE_RECURRING)
        assert view._model.item(0, 3).text() == "2024-02-01"

    def test_row_data_status_column(self, qapp) -> None:
        """Fifth column must show the status."""
        view = _make_view(qapp, items=_SAMPLE_RECURRING)
        assert view._model.item(0, 4).text() == "active"
        assert view._model.item(2, 4).text() == "paused"

    def test_recurring_invoice_id_stored_as_user_role(self, qapp) -> None:
        """The id must be stored as UserRole on the name column item."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_RECURRING)
        stored_id = view._model.item(0, 0).data(Qt.ItemDataRole.UserRole)
        assert stored_id == "ri-001"

    def test_empty_state_zero_rows(self, qapp) -> None:
        """When service returns empty list, model must have 0 rows."""
        view = _make_view(qapp, items=[])
        assert view._model.rowCount() == 0


# ---------------------------------------------------------------------------
# Tests — Offline
# ---------------------------------------------------------------------------


class TestRecurringInvoicesViewOffline:
    def test_offline_banner_shown_on_server_error(self, qapp) -> None:
        """Offline banner must be visible when service raises ServerOfflineError."""
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _make_view(qapp, side_effect=ServerOfflineError("offline"))
        assert not view._offline_label.isHidden()

    def test_offline_banner_hidden_when_data_loads(self, qapp) -> None:
        """Offline banner must be hidden when data loads successfully."""
        view = _make_view(qapp, items=_SAMPLE_RECURRING)
        assert view._offline_label.isHidden()


# ---------------------------------------------------------------------------
# Tests — Filter toolbar
# ---------------------------------------------------------------------------


class TestRecurringInvoicesViewFilterToolbar:
    def test_has_status_combo(self, qapp) -> None:
        """View must expose a status filter QComboBox."""
        from PySide6.QtWidgets import QComboBox

        view = _make_view(qapp, items=[])
        assert isinstance(view._status_combo, QComboBox)

    def test_status_combo_options(self, qapp) -> None:
        """Status combo must contain All, Active, Paused, Ended."""
        view = _make_view(qapp, items=[])
        options = [
            view._status_combo.itemText(i)
            for i in range(view._status_combo.count())
        ]
        assert options == ["All", "Active", "Paused", "Ended"]

    def test_has_new_recurring_invoice_button(self, qapp) -> None:
        """View must expose a New Recurring Invoice QPushButton."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._new_btn, QPushButton)
        assert view._new_btn.text() == "New Recurring Invoice"

    def test_has_run_now_button(self, qapp) -> None:
        """View must expose a Run Now QPushButton."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._run_now_btn, QPushButton)
        assert view._run_now_btn.text() == "Run Now"

    def test_run_now_disabled_initially(self, qapp) -> None:
        """Run Now button must be disabled when nothing is selected."""
        view = _make_view(qapp, items=_SAMPLE_RECURRING)
        assert not view._run_now_btn.isEnabled()

    def test_status_filter_triggers_reload(self, qapp) -> None:
        """Changing the status combo must trigger a fresh load (page reset to 1)."""
        from PySide6.QtWidgets import QApplication

        call_count = 0

        def _side_effect(client, page=1, page_size=50, **kwargs):
            nonlocal call_count
            call_count += 1
            return []

        with patch(_PATCH_LIST, side_effect=_side_effect):
            from saebooks_desktop.views.recurring_invoices import RecurringInvoicesView

            view = RecurringInvoicesView()
            before = call_count
            view._status_combo.setCurrentIndex(1)  # select "Active"
            QApplication.processEvents()
            assert call_count > before, "list_recurring_invoices should have been called again"


# ---------------------------------------------------------------------------
# Tests — Double-click
# ---------------------------------------------------------------------------


class TestRecurringInvoicesViewDoubleClick:
    def test_double_click_emits_recurring_invoice_selected(self, qapp) -> None:
        """Double-clicking a row must emit recurring_invoice_selected with the id."""
        view = _make_view(qapp, items=_SAMPLE_RECURRING)

        received: list[str] = []
        view.recurring_invoice_selected.connect(received.append)

        index = view._model.index(0, 0)
        view._on_double_click(index)

        assert received == ["ri-001"]

    def test_double_click_second_row(self, qapp) -> None:
        """Double-clicking row 1 must emit the id of the second recurring invoice."""
        view = _make_view(qapp, items=_SAMPLE_RECURRING)

        received: list[str] = []
        view.recurring_invoice_selected.connect(received.append)

        index = view._model.index(1, 0)
        view._on_double_click(index)

        assert received == ["ri-002"]

    def test_new_recurring_invoice_signal_emitted(self, qapp) -> None:
        """Clicking New Recurring Invoice must emit new_recurring_invoice_requested."""
        view = _make_view(qapp, items=[])

        triggered = []
        view.new_recurring_invoice_requested.connect(lambda: triggered.append(True))
        view._new_btn.click()

        assert triggered == [True]


# ---------------------------------------------------------------------------
# Tests — Run Now action
# ---------------------------------------------------------------------------


class TestRecurringInvoicesViewRunNow:
    def test_run_now_calls_service(self, qapp) -> None:
        """_on_run_now_clicked must call run_recurring_invoice with the selected id."""
        view = _make_view(qapp, items=_SAMPLE_RECURRING)

        # Select row 0 programmatically
        view._table.selectRow(0)

        with patch(_PATCH_RUN, return_value={"id": "inv-new-001"}) as mock_run:
            view._on_run_now_clicked()

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][1] == "ri-001"  # second positional arg is the id

    def test_run_now_shows_success_banner(self, qapp) -> None:
        """Run Now must show the success banner after a successful call."""
        view = _make_view(qapp, items=_SAMPLE_RECURRING)
        view._table.selectRow(0)

        with patch(_PATCH_RUN, return_value={"id": "inv-new-001"}):
            view._on_run_now_clicked()

        assert not view._offline_label.isHidden()
        assert "generated" in view._offline_label.text().lower()

    def test_run_now_shows_error_on_api_failure(self, qapp) -> None:
        """Run Now must not crash when the API raises APIError."""
        from PySide6.QtWidgets import QMessageBox

        from saebooks_desktop.services.api_client import APIError

        view = _make_view(qapp, items=_SAMPLE_RECURRING)
        view._table.selectRow(0)

        with (
            patch(_PATCH_RUN, side_effect=APIError("server error", status_code=500)),
            patch.object(QMessageBox, "critical", return_value=None),
        ):
            try:
                view._on_run_now_clicked()
            except Exception:  # noqa: BLE001
                pytest.fail("_on_run_now_clicked raised unexpectedly on APIError")


# ---------------------------------------------------------------------------
# Tests — Pagination
# ---------------------------------------------------------------------------


class TestRecurringInvoicesViewPagination:
    def test_load_more_button_exists(self, qapp) -> None:
        """View must expose a Load more QPushButton."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._load_more_btn, QPushButton)

    def test_load_more_disabled_when_fewer_than_page_size(self, qapp) -> None:
        """Load more must be disabled when fewer than 50 items are returned."""
        view = _make_view(qapp, items=_SAMPLE_RECURRING)
        assert not view._load_more_btn.isEnabled()

    def test_load_more_appends_rows(self, qapp) -> None:
        """Clicking Load more must append the next page to the existing rows."""
        _PAGE_SIZE = 50
        page_1 = (_SAMPLE_RECURRING * 20)[:_PAGE_SIZE]

        extra_ri = {
            "id": "ri-extra",
            "name": "Quarterly Report",
            "contact_name": "Extra Co",
            "frequency": "quarterly",
            "next_date": "2024-04-01",
            "status": "active",
        }

        with patch(_PATCH_LIST, return_value=page_1):
            from saebooks_desktop.views.recurring_invoices import RecurringInvoicesView

            view = RecurringInvoicesView()

        rows_after_first_load = view._model.rowCount()
        assert rows_after_first_load == _PAGE_SIZE

        with patch(_PATCH_LIST, return_value=[extra_ri]):
            view._on_load_more()

        assert view._model.rowCount() == rows_after_first_load + 1
        assert (
            view._model.item(rows_after_first_load, 0).text() == "Quarterly Report"
        )
