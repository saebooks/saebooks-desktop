"""Tests for CashbookView — offscreen Qt, mocked cashbook service layer.

All tests run without a real API server. ``saebooks_desktop.services.cashbook``
functions are patched at their import point inside
``saebooks_desktop.views.cashbook`` so no HTTP calls are made.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


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

_SAMPLE_CATEGORIES = [
    {
        "code": "sales",
        "label": "Sales",
        "group": "income",
        "direction": "income",
        "gst_default": "0.10",
        "hint_text": None,
    },
    {
        "code": "office_supplies",
        "label": "Office Supplies",
        "group": "expense",
        "direction": "expense",
        "gst_default": "0.10",
        "hint_text": None,
    },
]

_SAMPLE_SUMMARY = {
    "from": "2024-01-01",
    "to": "2024-12-31",
    "income_total": "150.00",
    "expense_total": "40.00",
    "net": "110.00",
    "by_category": [],
    "gst_collected": "13.64",
    "gst_paid": "3.64",
}

_SAMPLE_ENTRIES = [
    {
        "id": "ce-001",
        "journal_entry_id": "je-001",
        "journal_entry_ref": "JE-0001",
        "entry_date": "2024-01-10",
        "description": "Cash sale",
        "amount": "150.00",
        "direction": "income",
        "category_code": "sales",
        "category_label": "Sales",
        "gst_amount": "13.64",
        "version": 1,
        "created_at": "2024-01-10T00:00:00Z",
        "posted_at": "2024-01-10T00:00:00Z",
        "status": "posted",
    },
    {
        "id": "ce-002",
        "journal_entry_id": "je-002",
        "journal_entry_ref": "JE-0002",
        "entry_date": "2024-01-15",
        "description": "Stationery",
        "amount": "40.00",
        "direction": "expense",
        "category_code": "office_supplies",
        "category_label": "Office Supplies",
        "gst_amount": "3.64",
        "version": 1,
        "created_at": "2024-01-15T00:00:00Z",
        "posted_at": "2024-01-15T00:00:00Z",
        "status": "posted",
    },
]

_PATCH_LIST_CATEGORIES = "saebooks_desktop.views.cashbook.list_categories"
_PATCH_GET_SUMMARY = "saebooks_desktop.views.cashbook.get_summary"
_PATCH_LIST_ENTRIES = "saebooks_desktop.views.cashbook.list_entries"
_PATCH_CREATE_ENTRY = "saebooks_desktop.views.cashbook.create_entry"
_PATCH_DELETE_ENTRY = "saebooks_desktop.views.cashbook.delete_entry"
# get_company/get_company_id back the period picker's fin_year_start_month
# lookup (CashbookView._fetch_fin_year_start_month) — MUST always be
# patched here too, never left to hit the real (unmocked) APIClient /
# QSettings. A real machine can have a company_id persisted in QSettings
# from prior manual app use (verified locally: get_company_id() returned a
# real value), which would otherwise make load() attempt a genuine network
# call during a "no HTTP calls" unit test.
_PATCH_GET_COMPANY = "saebooks_desktop.views.cashbook.get_company"
_PATCH_GET_COMPANY_ID = "saebooks_desktop.views.cashbook.get_company_id"


def _make_view(
    qapp,
    categories=None,
    summary=None,
    entries=None,
    categories_side_effect=None,
    summary_side_effect=None,
    entries_side_effect=None,
    fin_year_start_month=None,
):
    from saebooks_desktop.views.cashbook import CashbookView

    cat_patch = (
        patch(_PATCH_LIST_CATEGORIES, side_effect=categories_side_effect)
        if categories_side_effect is not None
        else patch(
            _PATCH_LIST_CATEGORIES,
            return_value=categories if categories is not None else [],
        )
    )
    summary_patch = (
        patch(_PATCH_GET_SUMMARY, side_effect=summary_side_effect)
        if summary_side_effect is not None
        else patch(
            _PATCH_GET_SUMMARY, return_value=summary if summary is not None else {}
        )
    )
    entries_patch = (
        patch(_PATCH_LIST_ENTRIES, side_effect=entries_side_effect)
        if entries_side_effect is not None
        else patch(
            _PATCH_LIST_ENTRIES, return_value=entries if entries is not None else []
        )
    )
    # Default: no company configured -> _fetch_fin_year_start_month short-
    # circuits to 7 without calling get_company at all (matches production
    # behaviour for a fresh install). Pass fin_year_start_month= to
    # exercise the "company IS configured" path deterministically instead.
    company_id_patch = patch(
        _PATCH_GET_COMPANY_ID,
        return_value="co-test" if fin_year_start_month is not None else "",
    )
    company_patch = patch(
        _PATCH_GET_COMPANY,
        return_value={"fin_year_start_month": fin_year_start_month},
    )

    with cat_patch, summary_patch, entries_patch, company_id_patch, company_patch:
        view = CashbookView()
        # Initial load moved from __init__ to first showEvent; trigger it
        # here explicitly while the service patches are still active.
        view._loaded_once = True
        view.load()
        return view


# ---------------------------------------------------------------------------
# Instantiation / table structure
# ---------------------------------------------------------------------------


class TestCashbookViewInstantiation:
    def test_instantiates_without_crash(self, qapp) -> None:
        view = _make_view(qapp)
        assert view is not None

    def test_uses_qtablewidget(self, qapp) -> None:
        from PySide6.QtWidgets import QTableWidget

        view = _make_view(qapp)
        assert isinstance(view._table, QTableWidget)

    def test_has_five_columns(self, qapp) -> None:
        view = _make_view(qapp)
        assert view._table.columnCount() == 5

    def test_column_headers(self, qapp) -> None:
        expected = ["Date", "Direction", "Category", "Description", "Amount"]
        view = _make_view(qapp)
        headers = [
            view._table.horizontalHeaderItem(i).text()
            for i in range(view._table.columnCount())
        ]
        assert headers == expected

    def test_has_add_entry_button(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp)
        assert isinstance(view._add_btn, QPushButton)
        assert view._add_btn.text() == "Add entry"

    def test_form_hidden_by_default(self, qapp) -> None:
        view = _make_view(qapp)
        assert view._form_widget.isHidden()


# ---------------------------------------------------------------------------
# Summary strip
# ---------------------------------------------------------------------------


class TestCashbookViewSummary:
    def test_summary_labels_populated(self, qapp) -> None:
        view = _make_view(qapp, summary=_SAMPLE_SUMMARY)
        assert "150.00" in view._money_in_label.text()
        assert "40.00" in view._money_out_label.text()
        assert "110.00" in view._net_label.text()

    def test_extract_summary_prefers_real_field_names(self, qapp) -> None:
        from saebooks_desktop.views.cashbook import _extract_summary

        result = _extract_summary(_SAMPLE_SUMMARY)
        assert result == {
            "income": "150.00",
            "expense": "40.00",
            "net": "110.00",
            "gst_collected": "13.64",
            "gst_paid": "3.64",
        }

    def test_extract_summary_falls_back_to_alternate_keys(self, qapp) -> None:
        from saebooks_desktop.views.cashbook import _extract_summary

        result = _extract_summary(
            {"money_in": "10.00", "money_out": "5.00", "net": "5.00"}
        )
        assert result == {
            "income": "10.00",
            "expense": "5.00",
            "net": "5.00",
            "gst_collected": "0",
            "gst_paid": "0",
        }

    def test_summary_strip_uses_brand_tax_label(self, qapp) -> None:
        """The GST strip labels carry the brand tax_label (GST vs käibemaks)."""
        view = _make_view(qapp, summary=_SAMPLE_SUMMARY)
        # Default brand is saebooks → "GST"
        assert view._gst_collected_label.text() == "GST collected: 13.64"
        assert view._gst_paid_label.text() == "GST paid: 3.64"

    def test_summary_strip_tasur_tax_label(self, qapp, monkeypatch) -> None:
        """SAEBOOKS_BRAND=tasur switches the strip wording to käibemaks."""
        monkeypatch.setenv("SAEBOOKS_BRAND", "tasur")
        view = _make_view(qapp, summary=_SAMPLE_SUMMARY)
        assert view._gst_collected_label.text() == "käibemaks collected: 13.64"
        assert view._gst_paid_label.text() == "käibemaks paid: 3.64"


# ---------------------------------------------------------------------------
# Entries table population
# ---------------------------------------------------------------------------


class TestCashbookViewEntries:
    def test_row_count_matches_entries(self, qapp) -> None:
        view = _make_view(qapp, entries=_SAMPLE_ENTRIES)
        assert view._table.rowCount() == 2

    def test_newest_first_ordering(self, qapp) -> None:
        view = _make_view(qapp, entries=_SAMPLE_ENTRIES)
        # ce-002 (2024-01-15) is newer than ce-001 (2024-01-10)
        assert view._table.item(0, 0).text() == "2024-01-15"
        assert view._table.item(1, 0).text() == "2024-01-10"

    def test_direction_rendered_as_in_out(self, qapp) -> None:
        view = _make_view(qapp, entries=_SAMPLE_ENTRIES)
        # row 0 is ce-002 (expense) after newest-first sort
        assert view._table.item(0, 1).text() == "Out"
        assert view._table.item(1, 1).text() == "In"

    def test_category_column(self, qapp) -> None:
        view = _make_view(qapp, entries=_SAMPLE_ENTRIES)
        assert view._table.item(1, 2).text() == "Sales"

    def test_description_column(self, qapp) -> None:
        view = _make_view(qapp, entries=_SAMPLE_ENTRIES)
        assert view._table.item(1, 3).text() == "Cash sale"

    def test_amount_column(self, qapp) -> None:
        view = _make_view(qapp, entries=_SAMPLE_ENTRIES)
        assert view._table.item(1, 4).text() == "150.00"

    def test_entry_id_stored_as_user_role(self, qapp) -> None:
        from PySide6.QtCore import Qt

        view = _make_view(qapp, entries=_SAMPLE_ENTRIES)
        stored_id = view._table.item(1, 0).data(Qt.ItemDataRole.UserRole)
        assert stored_id == "ce-001"

    def test_empty_state_zero_rows(self, qapp) -> None:
        view = _make_view(qapp, entries=[])
        assert view._table.rowCount() == 0


# ---------------------------------------------------------------------------
# Offline / module-unavailable banners
# ---------------------------------------------------------------------------


class TestCashbookViewDegradedStates:
    def test_offline_banner_shown_on_server_error(self, qapp) -> None:
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _make_view(
            qapp, categories_side_effect=ServerOfflineError("offline")
        )
        assert not view._offline_banner.isHidden()
        assert view._offline_banner.objectName() == "offline_banner"

    def test_offline_banner_hidden_on_success(self, qapp) -> None:
        view = _make_view(qapp, entries=_SAMPLE_ENTRIES)
        assert view._offline_banner.isHidden()

    def test_module_banner_shown_on_module_unavailable(self, qapp) -> None:
        from saebooks_desktop.services.api_client import ModuleUnavailableError

        view = _make_view(
            qapp,
            categories_side_effect=ModuleUnavailableError(
                "The cashbook module is temporarily unavailable.", module="cashbook"
            ),
        )
        assert not view._module_banner.isHidden()
        assert view._module_banner.objectName() == "module_banner"
        assert "cashbook" in view._module_banner.text().lower()

    def test_add_button_disabled_on_module_unavailable(self, qapp) -> None:
        from saebooks_desktop.services.api_client import ModuleUnavailableError

        view = _make_view(
            qapp,
            categories_side_effect=ModuleUnavailableError(
                "unavailable", module="cashbook"
            ),
        )
        assert not view._add_btn.isEnabled()

    def test_load_never_raises_on_generic_error(self, qapp) -> None:
        # Any other exception must be swallowed, not propagated.
        view = _make_view(qapp, categories_side_effect=RuntimeError("boom"))
        assert view is not None


# ---------------------------------------------------------------------------
# Add-entry flow
# ---------------------------------------------------------------------------


class TestCashbookViewAddEntry:
    def test_add_button_shows_form(self, qapp) -> None:
        view = _make_view(qapp, categories=_SAMPLE_CATEGORIES)
        view._add_btn.click()
        assert not view._form_widget.isHidden()

    def test_cancel_hides_form(self, qapp) -> None:
        view = _make_view(qapp, categories=_SAMPLE_CATEGORIES)
        view._add_btn.click()
        assert not view._form_widget.isHidden()
        view._cancel_btn.click()
        assert view._form_widget.isHidden()

    def test_category_combo_filtered_by_direction(self, qapp) -> None:
        view = _make_view(qapp, categories=_SAMPLE_CATEGORIES)
        view._add_btn.click()
        # Default direction is Income (index 0) -> only "Sales" should show.
        codes = [
            view._category_combo.itemData(i)
            for i in range(view._category_combo.count())
        ]
        assert codes == ["sales"]

    def test_category_combo_refilters_on_direction_change(self, qapp) -> None:
        view = _make_view(qapp, categories=_SAMPLE_CATEGORIES)
        view._add_btn.click()
        view._direction_combo.setCurrentIndex(1)  # Expense
        codes = [
            view._category_combo.itemData(i)
            for i in range(view._category_combo.count())
        ]
        assert codes == ["office_supplies"]

    def test_save_calls_create_entry_with_well_formed_body(self, qapp) -> None:
        view = _make_view(qapp, categories=_SAMPLE_CATEGORIES)
        view._add_btn.click()
        view._direction_combo.setCurrentIndex(1)  # Expense -> office_supplies
        view._description_edit.setText("New chairs")
        view._amount_edit.setText("99.50")

        with patch(
            _PATCH_CREATE_ENTRY, return_value={"id": "ce-new"}
        ) as mock_create, patch(_PATCH_LIST_ENTRIES, return_value=[]), patch(
            _PATCH_GET_SUMMARY, return_value={}
        ), patch(
            _PATCH_LIST_CATEGORIES, return_value=_SAMPLE_CATEGORIES
        ):
            view._on_save_clicked()

        assert mock_create.call_count == 1
        args, kwargs = mock_create.call_args
        body = args[1]
        assert body["direction"] == "expense"
        assert body["category_code"] == "office_supplies"
        assert body["description"] == "New chairs"
        assert body["amount"] == "99.50"
        assert "entry_date" in body

    def test_save_emits_entry_created(self, qapp) -> None:
        view = _make_view(qapp, categories=_SAMPLE_CATEGORIES)
        view._add_btn.click()
        view._direction_combo.setCurrentIndex(1)
        view._amount_edit.setText("10.00")

        received: list[str] = []
        view.entry_created.connect(received.append)

        with patch(_PATCH_CREATE_ENTRY, return_value={"id": "ce-new"}), patch(
            _PATCH_LIST_ENTRIES, return_value=[]
        ), patch(_PATCH_GET_SUMMARY, return_value={}), patch(
            _PATCH_LIST_CATEGORIES, return_value=_SAMPLE_CATEGORIES
        ), patch(_PATCH_GET_COMPANY_ID, return_value=""), patch(
            _PATCH_GET_COMPANY, return_value={}
        ):
            view._on_save_clicked()

        assert received == ["ce-new"]

    def test_save_hides_form_on_success(self, qapp) -> None:
        view = _make_view(qapp, categories=_SAMPLE_CATEGORIES)
        view._add_btn.click()
        view._direction_combo.setCurrentIndex(1)
        view._amount_edit.setText("10.00")

        with patch(_PATCH_CREATE_ENTRY, return_value={"id": "ce-new"}), patch(
            _PATCH_LIST_ENTRIES, return_value=[]
        ), patch(_PATCH_GET_SUMMARY, return_value={}), patch(
            _PATCH_LIST_CATEGORIES, return_value=_SAMPLE_CATEGORIES
        ), patch(_PATCH_GET_COMPANY_ID, return_value=""), patch(
            _PATCH_GET_COMPANY, return_value={}
        ):
            view._on_save_clicked()

        assert view._form_widget.isHidden()

    def test_save_without_category_shows_error(self, qapp) -> None:
        view = _make_view(qapp, categories=[])
        view._add_btn.click()
        view._amount_edit.setText("10.00")

        with patch(_PATCH_CREATE_ENTRY) as mock_create:
            view._on_save_clicked()

        mock_create.assert_not_called()
        assert not view._form_error_label.isHidden()

    def test_save_with_invalid_amount_shows_error(self, qapp) -> None:
        view = _make_view(qapp, categories=_SAMPLE_CATEGORIES)
        view._add_btn.click()
        view._direction_combo.setCurrentIndex(1)
        view._amount_edit.setText("")

        with patch(_PATCH_CREATE_ENTRY) as mock_create:
            view._on_save_clicked()

        mock_create.assert_not_called()
        assert not view._form_error_label.isHidden()

    def test_save_with_zero_amount_shows_error(self, qapp) -> None:
        view = _make_view(qapp, categories=_SAMPLE_CATEGORIES)
        view._add_btn.click()
        view._direction_combo.setCurrentIndex(1)
        # Bypass the QDoubleValidator by setting the underlying text directly.
        view._amount_edit.setText("0")

        with patch(_PATCH_CREATE_ENTRY) as mock_create:
            view._on_save_clicked()

        mock_create.assert_not_called()
        assert not view._form_error_label.isHidden()


# ---------------------------------------------------------------------------
# Delete flow
# ---------------------------------------------------------------------------


class TestCashbookViewDeleteEntry:
    def test_delete_without_selection_does_nothing(self, qapp) -> None:
        view = _make_view(qapp, entries=_SAMPLE_ENTRIES)
        view._table.clearSelection()
        view._table.setCurrentCell(-1, -1)

        with patch(_PATCH_DELETE_ENTRY) as mock_delete:
            view._on_delete_clicked()

        mock_delete.assert_not_called()

    def test_delete_confirmed_calls_delete_entry(self, qapp) -> None:
        from PySide6.QtWidgets import QMessageBox

        view = _make_view(qapp, entries=_SAMPLE_ENTRIES)
        view._table.setCurrentCell(0, 0)

        with patch(_PATCH_DELETE_ENTRY, return_value=204) as mock_delete, patch(
            _PATCH_LIST_ENTRIES, return_value=[]
        ), patch(_PATCH_GET_SUMMARY, return_value={}), patch(
            _PATCH_LIST_CATEGORIES, return_value=[]
        ), patch(
            _PATCH_GET_COMPANY_ID, return_value=""
        ), patch(
            _PATCH_GET_COMPANY, return_value={}
        ), patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            view._on_delete_clicked()

        mock_delete.assert_called_once()

    def test_delete_declined_does_not_call_delete_entry(self, qapp) -> None:
        from PySide6.QtWidgets import QMessageBox

        view = _make_view(qapp, entries=_SAMPLE_ENTRIES)
        view._table.setCurrentCell(0, 0)

        with patch(_PATCH_DELETE_ENTRY) as mock_delete, patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.StandardButton.No,
        ):
            view._on_delete_clicked()

        mock_delete.assert_not_called()


# ---------------------------------------------------------------------------
# Period picker
# ---------------------------------------------------------------------------


class TestCashbookViewPeriodPicker:
    def test_combo_has_five_presets_defaulting_to_calendar_ytd(self, qapp) -> None:
        view = _make_view(qapp)
        assert view._period_combo.count() == 5
        assert view._period_combo.currentData() == "calendar_ytd"

    def test_period_label_shows_resolved_range(self, qapp) -> None:
        view = _make_view(qapp, summary=_SAMPLE_SUMMARY)
        # calendar_ytd with no company configured -> Jan 1 this year -> today.
        import datetime

        today = datetime.date.today()
        assert view._period_label.text() == f"{today.year}-01-01 → {today.isoformat()}"

    def test_get_summary_called_with_resolved_dates(self, qapp) -> None:
        import datetime

        today = datetime.date.today()
        with patch(_PATCH_LIST_CATEGORIES, return_value=[]), patch(
            _PATCH_GET_SUMMARY, return_value={}
        ) as mock_summary, patch(_PATCH_LIST_ENTRIES, return_value=[]), patch(
            _PATCH_GET_COMPANY_ID, return_value=""
        ), patch(_PATCH_GET_COMPANY, return_value={}):
            from saebooks_desktop.views.cashbook import CashbookView

            view = CashbookView()
            view._loaded_once = True
            view.load()

        mock_summary.assert_called_once()
        _client_arg = mock_summary.call_args.args[0]
        assert mock_summary.call_args.kwargs["date_from"] == f"{today.year}-01-01"
        assert mock_summary.call_args.kwargs["date_to"] == today.isoformat()

    def test_this_fy_preset_uses_company_fin_year_start_month(self, qapp) -> None:
        """A calendar-year-FY company (fin_year_start_month=1) resolves
        'this_fy' the same as calendar_ytd — both start 1 January."""
        import datetime

        today = datetime.date.today()
        with patch(_PATCH_LIST_CATEGORIES, return_value=[]), patch(
            _PATCH_GET_SUMMARY, return_value={}
        ) as mock_summary, patch(_PATCH_LIST_ENTRIES, return_value=[]), patch(
            _PATCH_GET_COMPANY_ID, return_value="co-test"
        ), patch(_PATCH_GET_COMPANY, return_value={"fin_year_start_month": 1}):
            from saebooks_desktop.views.cashbook import CashbookView

            view = CashbookView()
            view._loaded_once = True
            view._period_combo.setCurrentIndex(0)  # "This FY"
            view.load()

        assert mock_summary.call_args.kwargs["date_from"] == f"{today.year}-01-01"

    def test_construction_does_not_reload_on_preset_wiring(self, qapp) -> None:
        with patch(_PATCH_LIST_CATEGORIES) as mock_cat, patch(
            _PATCH_GET_SUMMARY
        ) as mock_summary, patch(_PATCH_LIST_ENTRIES) as mock_entries:
            from saebooks_desktop.views.cashbook import CashbookView

            CashbookView()
        mock_cat.assert_not_called()
        mock_summary.assert_not_called()
        mock_entries.assert_not_called()

    def test_changing_preset_reloads(self, qapp) -> None:
        view = _make_view(qapp, summary=_SAMPLE_SUMMARY)
        with patch(_PATCH_LIST_CATEGORIES, return_value=[]), patch(
            _PATCH_GET_SUMMARY, return_value={}
        ) as mock_summary, patch(_PATCH_LIST_ENTRIES, return_value=[]), patch(
            _PATCH_GET_COMPANY_ID, return_value=""
        ), patch(_PATCH_GET_COMPANY, return_value={}):
            view._period_combo.setCurrentIndex(4)  # "This quarter"

        mock_summary.assert_called_once()
