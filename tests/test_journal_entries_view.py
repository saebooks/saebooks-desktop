"""Tests for JournalEntriesView — offscreen Qt, mocked API service layer.

All tests run without a real API server.  The service function
``saebooks_desktop.services.journal_entries.list_journal_entries`` is
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

_SAMPLE_JOURNALS = [
    {
        "id": "je-001",
        "date": "2024-01-15",
        "reference": "JNL-0001",
        "source": "manual",
        "narration": "Opening entry",
        "dr_total": "10000.00",
        "cr_total": "10000.00",
    },
    {
        "id": "je-002",
        "date": "2024-01-20",
        "reference": "JNL-0002",
        "source": "invoice",
        "narration": "Sales invoice INV-0001",
        "dr_total": "1500.00",
        "cr_total": "1500.00",
    },
    {
        "id": "je-003",
        "date": "2024-01-25",
        "reference": "JNL-0003",
        "source": "bill",
        "narration": "Supplier bill BILL-0001",
        "dr_total": "800.00",
        "cr_total": "800.00",
    },
]


# ---------------------------------------------------------------------------
# Helper to build a view with a mocked list_journal_entries
# ---------------------------------------------------------------------------


def _make_view(qapp, items=None, side_effect=None):
    """Create JournalEntriesView with list_journal_entries patched."""
    from saebooks_desktop.views.journal_entries import JournalEntriesView

    if side_effect is not None:
        with patch(
            "saebooks_desktop.views.journal_entries.list_journal_entries",
            side_effect=side_effect,
        ):
            return JournalEntriesView()
    else:
        with patch(
            "saebooks_desktop.views.journal_entries.list_journal_entries",
            return_value=items if items is not None else [],
        ):
            return JournalEntriesView()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestJournalEntriesViewInstantiation:
    def test_instantiates_without_crash(self, qapp) -> None:
        """JournalEntriesView must create without raising when API is mocked."""
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
        """Column headers must match the spec exactly."""
        expected = ["Date", "Reference", "Source", "Narration", "Dr Total", "Cr Total"]
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


class TestJournalEntriesViewModelPopulation:
    def test_row_count_matches_items(self, qapp) -> None:
        """Model must have one row per journal entry returned by the service."""
        view = _make_view(qapp, items=_SAMPLE_JOURNALS)
        assert view._model.rowCount() == 3

    def test_row_data_date_column(self, qapp) -> None:
        """First column must show the journal date."""
        view = _make_view(qapp, items=_SAMPLE_JOURNALS)
        assert view._model.item(0, 0).text() == "2024-01-15"
        assert view._model.item(1, 0).text() == "2024-01-20"

    def test_row_data_reference_column(self, qapp) -> None:
        """Second column must show the reference."""
        view = _make_view(qapp, items=_SAMPLE_JOURNALS)
        assert view._model.item(0, 1).text() == "JNL-0001"

    def test_row_data_source_column(self, qapp) -> None:
        """Third column must show the source."""
        view = _make_view(qapp, items=_SAMPLE_JOURNALS)
        assert view._model.item(0, 2).text() == "manual"
        assert view._model.item(1, 2).text() == "invoice"
        assert view._model.item(2, 2).text() == "bill"

    def test_row_data_narration_column(self, qapp) -> None:
        """Fourth column must show the narration."""
        view = _make_view(qapp, items=_SAMPLE_JOURNALS)
        assert view._model.item(0, 3).text() == "Opening entry"

    def test_dr_total_column(self, qapp) -> None:
        """Fifth column must show the Dr total."""
        view = _make_view(qapp, items=_SAMPLE_JOURNALS)
        assert view._model.item(0, 4).text() == "10000.00"

    def test_cr_total_column(self, qapp) -> None:
        """Sixth column must show the Cr total."""
        view = _make_view(qapp, items=_SAMPLE_JOURNALS)
        assert view._model.item(0, 5).text() == "10000.00"

    def test_dr_total_right_aligned(self, qapp) -> None:
        """Dr Total column items must be right-aligned."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_JOURNALS)
        dr_item = view._model.item(0, 4)
        alignment = dr_item.textAlignment()
        assert alignment & Qt.AlignmentFlag.AlignRight

    def test_cr_total_right_aligned(self, qapp) -> None:
        """Cr Total column items must be right-aligned."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_JOURNALS)
        cr_item = view._model.item(0, 5)
        alignment = cr_item.textAlignment()
        assert alignment & Qt.AlignmentFlag.AlignRight

    def test_journal_id_stored_as_user_role(self, qapp) -> None:
        """The journal id must be stored as UserRole on the date column item."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_JOURNALS)
        stored_id = view._model.item(0, 0).data(Qt.ItemDataRole.UserRole)
        assert stored_id == "je-001"

    def test_empty_state_zero_rows(self, qapp) -> None:
        """When service returns empty list, model must have 0 rows."""
        view = _make_view(qapp, items=[])
        assert view._model.rowCount() == 0


class TestJournalEntriesViewOffline:
    def test_offline_banner_shown_on_server_error(self, qapp) -> None:
        """Offline banner must be visible when service raises ServerOfflineError."""
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _make_view(qapp, side_effect=ServerOfflineError("offline"))
        assert not view._offline_label.isHidden()

    def test_offline_banner_hidden_when_data_loads(self, qapp) -> None:
        """Offline banner must be hidden when data loads successfully."""
        view = _make_view(qapp, items=_SAMPLE_JOURNALS)
        assert view._offline_label.isHidden()


class TestJournalEntriesViewFilterToolbar:
    def test_has_source_combo(self, qapp) -> None:
        """View must expose a source filter QComboBox."""
        from PySide6.QtWidgets import QComboBox

        view = _make_view(qapp, items=[])
        assert isinstance(view._source_combo, QComboBox)

    def test_source_combo_options(self, qapp) -> None:
        """Source combo must contain All, Manual, Invoice, Bill, Payment, Reconciliation."""
        view = _make_view(qapp, items=[])
        options = [
            view._source_combo.itemText(i)
            for i in range(view._source_combo.count())
        ]
        assert options == [
            "All",
            "Manual",
            "Invoice",
            "Bill",
            "Payment",
            "Reconciliation",
        ]

    def test_has_new_journal_button(self, qapp) -> None:
        """View must expose a New Journal QPushButton."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._new_btn, QPushButton)
        assert view._new_btn.text() == "New Journal"

    def test_source_filter_triggers_reload(self, qapp) -> None:
        """Changing the source combo must trigger a fresh load (page reset to 1)."""
        from PySide6.QtWidgets import QApplication

        call_count = 0

        def _side_effect(client, page=1, page_size=50, **kwargs):
            nonlocal call_count
            call_count += 1
            return []

        with patch(
            "saebooks_desktop.views.journal_entries.list_journal_entries",
            side_effect=_side_effect,
        ):
            from saebooks_desktop.views.journal_entries import JournalEntriesView

            view = JournalEntriesView()
            before = call_count
            view._source_combo.setCurrentIndex(1)  # select "Manual"
            QApplication.processEvents()
            assert call_count > before, "list_journal_entries should have been called again"


class TestJournalEntriesViewDoubleClick:
    def test_double_click_emits_journal_selected(self, qapp) -> None:
        """Double-clicking a row must emit journal_selected with the journal id."""
        view = _make_view(qapp, items=_SAMPLE_JOURNALS)

        received: list[str] = []
        view.journal_selected.connect(received.append)

        index = view._model.index(0, 0)
        view._on_double_click(index)

        assert received == ["je-001"]

    def test_double_click_second_row(self, qapp) -> None:
        """Double-clicking row 1 must emit the id of the second journal."""
        view = _make_view(qapp, items=_SAMPLE_JOURNALS)

        received: list[str] = []
        view.journal_selected.connect(received.append)

        index = view._model.index(1, 0)
        view._on_double_click(index)

        assert received == ["je-002"]

    def test_new_journal_signal_emitted(self, qapp) -> None:
        """Clicking New Journal must emit new_journal_requested."""
        view = _make_view(qapp, items=[])

        triggered = []
        view.new_journal_requested.connect(lambda: triggered.append(True))
        view._new_btn.click()

        assert triggered == [True]


class TestJournalEntriesViewPagination:
    def test_load_more_button_exists(self, qapp) -> None:
        """View must expose a Load more QPushButton."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._load_more_btn, QPushButton)

    def test_load_more_disabled_when_fewer_than_page_size(self, qapp) -> None:
        """Load more must be disabled when fewer than 50 items are returned."""
        view = _make_view(qapp, items=_SAMPLE_JOURNALS)  # only 3 items
        assert not view._load_more_btn.isEnabled()

    def test_load_more_appends_rows(self, qapp) -> None:
        """Clicking Load more must append the next page to the existing rows."""
        _PAGE_SIZE = 50
        page_1 = (_SAMPLE_JOURNALS * 20)[:_PAGE_SIZE]  # exactly 50 items

        extra_journal = {
            "id": "je-extra",
            "date": "2024-02-01",
            "reference": "JNL-EXTRA",
            "source": "manual",
            "narration": "Extra entry",
            "dr_total": "500.00",
            "cr_total": "500.00",
        }

        with patch(
            "saebooks_desktop.views.journal_entries.list_journal_entries",
            return_value=page_1,
        ):
            from saebooks_desktop.views.journal_entries import JournalEntriesView

            view = JournalEntriesView()

        rows_after_first_load = view._model.rowCount()
        assert rows_after_first_load == _PAGE_SIZE

        with patch(
            "saebooks_desktop.views.journal_entries.list_journal_entries",
            return_value=[extra_journal],
        ):
            view._on_load_more()

        assert view._model.rowCount() == rows_after_first_load + 1
        assert view._model.item(rows_after_first_load, 1).text() == "JNL-EXTRA"
