"""Tests for ContactsView — offscreen Qt, mocked API service layer.

All tests run without a real API server.  The service function
``saebooks_desktop.services.contacts.list_contacts`` is patched at the
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

_SAMPLE_CONTACTS = [
    {
        "id": "con-001",
        "name": "Acme Corp",
        "type": "customer",
        "email": "acme@example.com",
        "phone": "0400 000 001",
        "balance": "1500.00",
    },
    {
        "id": "con-002",
        "name": "Beta Supplies",
        "type": "supplier",
        "email": "beta@example.com",
        "phone": "0400 000 002",
        "balance": "250.00",
    },
    {
        "id": "con-003",
        "name": "Charlie Smith",
        "type": "employee",
        "email": "charlie@example.com",
        "phone": "0400 000 003",
        "balance": "0.00",
    },
]

_PATCH_TARGET = "saebooks_desktop.views.contacts_view.list_contacts"


# ---------------------------------------------------------------------------
# Helper to build a view with a mocked list_contacts
# ---------------------------------------------------------------------------


def _make_view(qapp, items=None, side_effect=None):
    """Create ContactsView with list_contacts patched to return *items*."""
    from saebooks_desktop.views.contacts_view import ContactsView

    if side_effect is not None:
        with patch(_PATCH_TARGET, side_effect=side_effect):
            return ContactsView()
    else:
        with patch(_PATCH_TARGET, return_value=items if items is not None else []):
            return ContactsView()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestContactsViewInstantiation:
    def test_instantiates_without_crash(self, qapp) -> None:
        """ContactsView must create without raising when API is mocked."""
        view = _make_view(qapp, items=[])
        assert view is not None

    def test_has_table_model(self, qapp) -> None:
        """View must expose a QStandardItemModel on _model."""
        from PySide6.QtGui import QStandardItemModel

        view = _make_view(qapp, items=[])
        assert isinstance(view._model, QStandardItemModel)

    def test_has_five_columns(self, qapp) -> None:
        """Model must have 5 columns: Name, Type, Email, Phone, Balance."""
        view = _make_view(qapp, items=[])
        assert view._model.columnCount() == 5

    def test_column_headers(self, qapp) -> None:
        """Column headers must match the spec exactly."""
        expected = ["Name", "Type", "Email", "Phone", "Balance"]
        view = _make_view(qapp, items=[])
        headers = [
            view._model.horizontalHeaderItem(i).text()
            for i in range(view._model.columnCount())
        ]
        assert headers == expected


class TestContactsViewModelPopulation:
    def test_row_count_matches_items(self, qapp) -> None:
        """Model must have one row per contact returned by the service."""
        view = _make_view(qapp, items=_SAMPLE_CONTACTS)
        assert view._model.rowCount() == 3

    def test_row_data_name_column(self, qapp) -> None:
        """First column must show the contact name."""
        view = _make_view(qapp, items=_SAMPLE_CONTACTS)
        assert view._model.item(0, 0).text() == "Acme Corp"
        assert view._model.item(1, 0).text() == "Beta Supplies"

    def test_row_data_type_column(self, qapp) -> None:
        """Second column must show the contact type."""
        view = _make_view(qapp, items=_SAMPLE_CONTACTS)
        assert view._model.item(0, 1).text() == "customer"
        assert view._model.item(1, 1).text() == "supplier"
        assert view._model.item(2, 1).text() == "employee"

    def test_row_data_email_column(self, qapp) -> None:
        """Third column must show the email address."""
        view = _make_view(qapp, items=_SAMPLE_CONTACTS)
        assert view._model.item(0, 2).text() == "acme@example.com"

    def test_row_data_phone_column(self, qapp) -> None:
        """Fourth column must show the phone number."""
        view = _make_view(qapp, items=_SAMPLE_CONTACTS)
        assert view._model.item(0, 3).text() == "0400 000 001"

    def test_balance_right_aligned(self, qapp) -> None:
        """Balance column items must be right-aligned."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_CONTACTS)
        balance_item = view._model.item(0, 4)
        alignment = balance_item.textAlignment()
        assert alignment & Qt.AlignmentFlag.AlignRight

    def test_contact_id_stored_as_user_role(self, qapp) -> None:
        """The contact id must be stored as UserRole on the name column item."""
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_CONTACTS)
        stored_id = view._model.item(0, 0).data(Qt.ItemDataRole.UserRole)
        assert stored_id == "con-001"

    def test_empty_state_zero_rows(self, qapp) -> None:
        """When service returns empty list, model must have 0 rows."""
        view = _make_view(qapp, items=[])
        assert view._model.rowCount() == 0


class TestContactsViewOffline:
    def test_offline_banner_shown_on_server_error(self, qapp) -> None:
        """Offline banner must be visible when service raises ServerOfflineError."""
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _make_view(qapp, side_effect=ServerOfflineError("offline"))
        assert not view._offline_label.isHidden()

    def test_offline_banner_hidden_when_data_loads(self, qapp) -> None:
        """Offline banner must be hidden when data loads successfully."""
        view = _make_view(qapp, items=_SAMPLE_CONTACTS)
        assert view._offline_label.isHidden()


class TestContactsViewFilterToolbar:
    def test_has_type_combo(self, qapp) -> None:
        """View must expose a type filter QComboBox."""
        from PySide6.QtWidgets import QComboBox

        view = _make_view(qapp, items=[])
        assert isinstance(view._type_combo, QComboBox)

    def test_type_combo_options(self, qapp) -> None:
        """Type combo must contain All, Customer, Supplier, Employee, Other."""
        view = _make_view(qapp, items=[])
        options = [
            view._type_combo.itemText(i)
            for i in range(view._type_combo.count())
        ]
        assert options == ["All", "Customer", "Supplier", "Employee", "Other"]

    def test_has_search_edit(self, qapp) -> None:
        """View must expose a search QLineEdit."""
        from PySide6.QtWidgets import QLineEdit

        view = _make_view(qapp, items=[])
        assert isinstance(view._search_edit, QLineEdit)

    def test_has_new_contact_button(self, qapp) -> None:
        """View must expose a New Contact QPushButton."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._new_btn, QPushButton)
        assert view._new_btn.text() == "New Contact"

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
            from saebooks_desktop.views.contacts_view import ContactsView

            view = ContactsView()
            before = call_count
            view._type_combo.setCurrentIndex(1)  # select "Customer"
            QApplication.processEvents()
            assert call_count > before, "list_contacts should have been called again"


class TestContactsViewDoubleClick:
    def test_double_click_emits_contact_selected(self, qapp) -> None:
        """Double-clicking a row must emit contact_selected with the contact id."""
        view = _make_view(qapp, items=_SAMPLE_CONTACTS)

        received: list[str] = []
        view.contact_selected.connect(received.append)

        index = view._model.index(0, 0)
        view._on_double_click(index)

        assert received == ["con-001"]

    def test_double_click_second_row(self, qapp) -> None:
        """Double-clicking row 1 must emit the id of the second contact."""
        view = _make_view(qapp, items=_SAMPLE_CONTACTS)

        received: list[str] = []
        view.contact_selected.connect(received.append)

        index = view._model.index(1, 0)
        view._on_double_click(index)

        assert received == ["con-002"]

    def test_new_contact_signal_emitted(self, qapp) -> None:
        """Clicking New Contact must emit new_contact_requested."""
        view = _make_view(qapp, items=[])

        triggered = []
        view.new_contact_requested.connect(lambda: triggered.append(True))
        view._new_btn.click()

        assert triggered == [True]


class TestContactsViewPagination:
    def test_load_more_button_exists(self, qapp) -> None:
        """View must expose a Load more QPushButton."""
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._load_more_btn, QPushButton)

    def test_load_more_disabled_when_fewer_than_page_size(self, qapp) -> None:
        """Load more must be disabled when fewer than 50 items are returned."""
        view = _make_view(qapp, items=_SAMPLE_CONTACTS)  # only 3 items
        assert not view._load_more_btn.isEnabled()

    def test_load_more_appends_rows(self, qapp) -> None:
        """Clicking Load more must append the next page to the existing rows."""
        _PAGE_SIZE = 50
        page_1 = (_SAMPLE_CONTACTS * 20)[:_PAGE_SIZE]  # exactly 50 items

        extra_contact = {
            "id": "con-extra",
            "name": "Extra Co",
            "type": "other",
            "email": "extra@example.com",
            "phone": "",
            "balance": "0.00",
        }

        with patch(_PATCH_TARGET, return_value=page_1):
            from saebooks_desktop.views.contacts_view import ContactsView

            view = ContactsView()

        rows_after_first_load = view._model.rowCount()
        assert rows_after_first_load == _PAGE_SIZE

        with patch(_PATCH_TARGET, return_value=[extra_contact]):
            view._on_load_more()

        assert view._model.rowCount() == rows_after_first_load + 1
        assert view._model.item(rows_after_first_load, 0).text() == "Extra Co"
