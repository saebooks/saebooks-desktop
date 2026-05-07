"""Tests for credit notes service and views — offscreen Qt, mocked API.

Covers:
  - saebooks_desktop.services.credit_notes (unit tests via APIClient mock)
  - saebooks_desktop.views.credit_notes.CreditNotesView (list view)
  - saebooks_desktop.views.credit_notes.CreditNoteForm (form view)
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

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
# Sample data
# ---------------------------------------------------------------------------

_UUID_CONTACT = "c0000000-0000-0000-0000-000000000001"
_UUID_ACCOUNT = "a0000000-0000-0000-0000-000000000001"
_UUID_TAX = "t0000000-0000-0000-0000-000000000001"

_SAMPLE_CREDIT_NOTES = [
    {
        "id": "cn-001",
        "number": "CN-0001",
        "contact_id": _UUID_CONTACT,
        "contact_name": "Acme Corp",
        "date": "2024-01-15",
        "total": "1500.00",
        "status": "posted",
    },
    {
        "id": "cn-002",
        "number": "CN-0002",
        "contact_id": _UUID_CONTACT,
        "contact_name": "Beta Ltd",
        "date": "2024-01-20",
        "total": "250.00",
        "status": "draft",
    },
    {
        "id": "cn-003",
        "number": "CN-0003",
        "contact_id": _UUID_CONTACT,
        "contact_name": "Gamma Inc",
        "date": "2024-01-25",
        "total": "800.00",
        "status": "voided",
    },
]

_SAMPLE_CONTACTS = [{"id": _UUID_CONTACT, "name": "Acme Corp"}]
_SAMPLE_ACCOUNTS = [{"id": _UUID_ACCOUNT, "name": "Sales Revenue"}]
_SAMPLE_TAX_CODES = [{"id": _UUID_TAX, "code": "GST10", "rate": 0.1}]

_SAMPLE_CN_DETAIL = {
    "id": "cn-001",
    "number": "CN-0001",
    "contact_id": _UUID_CONTACT,
    "date": "2024-01-15",
    "reference": "INV-ORIG-001",
    "version": 1,
    "status": "draft",
    "lines": [
        {
            "description": "Refund — consulting",
            "account_id": _UUID_ACCOUNT,
            "quantity": "1",
            "unit_price": "500.00",
            "tax_code_id": _UUID_TAX,
            "line_total": "550.00",
        }
    ],
}


# ===========================================================================
# Service layer tests
# ===========================================================================


class TestListCreditNotesService:
    def test_calls_correct_endpoint(self) -> None:
        from saebooks_desktop.services.credit_notes import list_credit_notes

        client = MagicMock()
        client.get.return_value = {"items": _SAMPLE_CREDIT_NOTES}
        result = list_credit_notes(client)
        client.get.assert_called_once_with(
            "/api/v1/credit_notes", params={"page": 1, "page_size": 50}
        )
        assert result == _SAMPLE_CREDIT_NOTES

    def test_status_filter_added_to_params(self) -> None:
        from saebooks_desktop.services.credit_notes import list_credit_notes

        client = MagicMock()
        client.get.return_value = {"items": []}
        list_credit_notes(client, status_filter="posted")
        call_params = client.get.call_args[1]["params"]
        assert call_params["status"] == "posted"

    def test_date_from_added_to_params(self) -> None:
        from saebooks_desktop.services.credit_notes import list_credit_notes

        client = MagicMock()
        client.get.return_value = {"items": []}
        list_credit_notes(client, date_from="2024-01-01")
        call_params = client.get.call_args[1]["params"]
        assert call_params["date_from"] == "2024-01-01"

    def test_returns_empty_list_when_no_items(self) -> None:
        from saebooks_desktop.services.credit_notes import list_credit_notes

        client = MagicMock()
        client.get.return_value = {}
        assert list_credit_notes(client) == []


class TestGetCreditNoteService:
    def test_calls_correct_endpoint(self) -> None:
        from saebooks_desktop.services.credit_notes import get_credit_note

        client = MagicMock()
        client.get.return_value = _SAMPLE_CN_DETAIL
        result = get_credit_note(client, "cn-001")
        client.get.assert_called_once_with("/api/v1/credit_notes/cn-001")
        assert result == _SAMPLE_CN_DETAIL


class TestCreateCreditNoteService:
    def test_calls_post_endpoint(self) -> None:
        from saebooks_desktop.services.credit_notes import create_credit_note

        client = MagicMock()
        client.post.return_value = {"id": "cn-new"}
        data = {"contact_id": _UUID_CONTACT, "date": "2024-02-01", "lines": []}
        result = create_credit_note(client, data)
        client.post.assert_called_once_with("/api/v1/credit_notes", json=data)
        assert result == {"id": "cn-new"}


class TestUpdateCreditNoteService:
    def test_calls_patch_with_if_match_header(self) -> None:
        from saebooks_desktop.services.credit_notes import update_credit_note

        client = MagicMock()
        client.patch.return_value = (200, {"id": "cn-001"})
        update_credit_note(client, "cn-001", {"date": "2024-02-01"}, etag=3)
        client.patch.assert_called_once_with(
            "/api/v1/credit_notes/cn-001",
            json={"date": "2024-02-01"},
            headers={"If-Match": "3"},
        )

    def test_returns_status_code_and_data(self) -> None:
        from saebooks_desktop.services.credit_notes import update_credit_note

        client = MagicMock()
        client.patch.return_value = (409, {"detail": "conflict"})
        status, data = update_credit_note(client, "cn-001", {}, etag=1)
        assert status == 409


class TestPostCreditNoteService:
    def test_calls_post_endpoint_with_if_match(self) -> None:
        from saebooks_desktop.services.credit_notes import post_credit_note

        client = MagicMock()
        client.post.return_value = {"id": "cn-001", "status": "posted"}
        post_credit_note(client, "cn-001", etag=2)
        client.post.assert_called_once_with(
            "/api/v1/credit_notes/cn-001/post", headers={"If-Match": "2"}
        )


class TestVoidCreditNoteService:
    def test_calls_void_endpoint(self) -> None:
        from saebooks_desktop.services.credit_notes import void_credit_note

        client = MagicMock()
        client.post.return_value = {"id": "cn-001", "status": "voided"}
        void_credit_note(client, "cn-001")
        client.post.assert_called_once_with("/api/v1/credit_notes/cn-001/void")


# ===========================================================================
# CreditNotesView (list view) tests
# ===========================================================================


def _make_cn_view(qapp, items=None, side_effect=None):
    from saebooks_desktop.views.credit_notes import CreditNotesView

    if side_effect is not None:
        with patch(
            "saebooks_desktop.views.credit_notes.list_credit_notes",
            side_effect=side_effect,
        ):
            return CreditNotesView()
    else:
        with patch(
            "saebooks_desktop.views.credit_notes.list_credit_notes",
            return_value=items if items is not None else [],
        ):
            return CreditNotesView()


class TestCreditNotesViewInstantiation:
    def test_instantiates_without_crash(self, qapp) -> None:
        view = _make_cn_view(qapp, items=[])
        assert view is not None

    def test_has_five_columns(self, qapp) -> None:
        view = _make_cn_view(qapp, items=[])
        assert view._model.columnCount() == 5

    def test_column_headers(self, qapp) -> None:
        expected = ["Number", "Contact", "Date", "Total", "Status"]
        view = _make_cn_view(qapp, items=[])
        headers = [
            view._model.horizontalHeaderItem(i).text()
            for i in range(view._model.columnCount())
        ]
        assert headers == expected

    def test_has_new_credit_note_button(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton

        view = _make_cn_view(qapp, items=[])
        assert isinstance(view._new_btn, QPushButton)
        assert view._new_btn.text() == "New Credit Note"

    def test_has_status_combo(self, qapp) -> None:
        from PySide6.QtWidgets import QComboBox

        view = _make_cn_view(qapp, items=[])
        assert isinstance(view._status_combo, QComboBox)

    def test_status_combo_options(self, qapp) -> None:
        view = _make_cn_view(qapp, items=[])
        options = [
            view._status_combo.itemText(i)
            for i in range(view._status_combo.count())
        ]
        assert options == ["All", "Draft", "Posted", "Voided"]


class TestCreditNotesViewModelPopulation:
    def test_row_count_matches_items(self, qapp) -> None:
        view = _make_cn_view(qapp, items=_SAMPLE_CREDIT_NOTES)
        assert view._model.rowCount() == 3

    def test_number_column(self, qapp) -> None:
        view = _make_cn_view(qapp, items=_SAMPLE_CREDIT_NOTES)
        assert view._model.item(0, 0).text() == "CN-0001"

    def test_contact_column(self, qapp) -> None:
        view = _make_cn_view(qapp, items=_SAMPLE_CREDIT_NOTES)
        assert view._model.item(0, 1).text() == "Acme Corp"

    def test_date_column(self, qapp) -> None:
        view = _make_cn_view(qapp, items=_SAMPLE_CREDIT_NOTES)
        assert view._model.item(0, 2).text() == "2024-01-15"

    def test_total_column(self, qapp) -> None:
        view = _make_cn_view(qapp, items=_SAMPLE_CREDIT_NOTES)
        assert view._model.item(0, 3).text() == "1500.00"

    def test_status_column(self, qapp) -> None:
        view = _make_cn_view(qapp, items=_SAMPLE_CREDIT_NOTES)
        assert view._model.item(0, 4).text() == "posted"
        assert view._model.item(1, 4).text() == "draft"
        assert view._model.item(2, 4).text() == "voided"

    def test_credit_note_id_stored_as_user_role(self, qapp) -> None:
        from PySide6.QtCore import Qt

        view = _make_cn_view(qapp, items=_SAMPLE_CREDIT_NOTES)
        stored_id = view._model.item(0, 0).data(Qt.ItemDataRole.UserRole)
        assert stored_id == "cn-001"

    def test_total_right_aligned(self, qapp) -> None:
        from PySide6.QtCore import Qt

        view = _make_cn_view(qapp, items=_SAMPLE_CREDIT_NOTES)
        item = view._model.item(0, 3)
        assert item.textAlignment() & Qt.AlignmentFlag.AlignRight

    def test_empty_state_zero_rows(self, qapp) -> None:
        view = _make_cn_view(qapp, items=[])
        assert view._model.rowCount() == 0


class TestCreditNotesViewOffline:
    def test_offline_banner_shown_on_error(self, qapp) -> None:
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _make_cn_view(qapp, side_effect=ServerOfflineError("offline"))
        assert not view._offline_label.isHidden()

    def test_offline_banner_hidden_on_success(self, qapp) -> None:
        view = _make_cn_view(qapp, items=_SAMPLE_CREDIT_NOTES)
        assert view._offline_label.isHidden()


class TestCreditNotesViewInteraction:
    def test_double_click_emits_credit_note_selected(self, qapp) -> None:
        view = _make_cn_view(qapp, items=_SAMPLE_CREDIT_NOTES)
        received: list[str] = []
        view.credit_note_selected.connect(received.append)
        index = view._model.index(0, 0)
        view._on_double_click(index)
        assert received == ["cn-001"]

    def test_new_credit_note_signal_emitted(self, qapp) -> None:
        view = _make_cn_view(qapp, items=[])
        triggered = []
        view.new_credit_note_requested.connect(lambda: triggered.append(True))
        view._new_btn.click()
        assert triggered == [True]

    def test_load_more_button_exists(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton

        view = _make_cn_view(qapp, items=[])
        assert isinstance(view._load_more_btn, QPushButton)

    def test_load_more_disabled_when_fewer_than_page_size(self, qapp) -> None:
        view = _make_cn_view(qapp, items=_SAMPLE_CREDIT_NOTES)
        assert not view._load_more_btn.isEnabled()


# ===========================================================================
# CreditNoteForm tests
# ===========================================================================

_PATCH_LIST_CONTACTS = "saebooks_desktop.views.credit_notes.list_contacts_for_credit_note"
_PATCH_LIST_ACCOUNTS = "saebooks_desktop.views.credit_notes.list_income_accounts_for_credit_note"
_PATCH_LIST_TAX = "saebooks_desktop.views.credit_notes.list_tax_codes_for_credit_note"
_PATCH_GET_CN = "saebooks_desktop.views.credit_notes.get_credit_note"
_PATCH_CREATE = "saebooks_desktop.views.credit_notes.create_credit_note"
_PATCH_UPDATE = "saebooks_desktop.views.credit_notes.update_credit_note"
_PATCH_POST = "saebooks_desktop.views.credit_notes.post_credit_note"


def _make_cn_form(qapp, credit_note_id=None, existing_data=None):
    """Create CreditNoteForm with all service calls mocked."""
    from saebooks_desktop.services.api_client import APIClient
    from saebooks_desktop.views.credit_notes import CreditNoteForm

    patches = {
        _PATCH_LIST_CONTACTS: _SAMPLE_CONTACTS,
        _PATCH_LIST_ACCOUNTS: _SAMPLE_ACCOUNTS,
        _PATCH_LIST_TAX: _SAMPLE_TAX_CODES,
    }
    with (
        patch(_PATCH_LIST_CONTACTS, return_value=_SAMPLE_CONTACTS),
        patch(_PATCH_LIST_ACCOUNTS, return_value=_SAMPLE_ACCOUNTS),
        patch(_PATCH_LIST_TAX, return_value=_SAMPLE_TAX_CODES),
        patch(_PATCH_GET_CN, return_value=existing_data or {}),
    ):
        return CreditNoteForm(APIClient(), credit_note_id=credit_note_id)


class TestCreditNoteFormInstantiation:
    def test_instantiates_without_crash(self, qapp) -> None:
        form = _make_cn_form(qapp)
        assert form is not None

    def test_has_contact_combo(self, qapp) -> None:
        from PySide6.QtWidgets import QComboBox

        form = _make_cn_form(qapp)
        assert isinstance(form._contact_combo, QComboBox)

    def test_has_date_edit(self, qapp) -> None:
        from PySide6.QtWidgets import QDateEdit

        form = _make_cn_form(qapp)
        assert isinstance(form._date_edit, QDateEdit)

    def test_starts_with_one_blank_line(self, qapp) -> None:
        form = _make_cn_form(qapp)
        assert form.line_count() == 1

    def test_has_save_draft_button(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton

        form = _make_cn_form(qapp)
        assert isinstance(form._save_draft_btn, QPushButton)
        assert form._save_draft_btn.text() == "Save as Draft"

    def test_has_save_post_button(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton

        form = _make_cn_form(qapp)
        assert isinstance(form._save_post_btn, QPushButton)
        assert "Post" in form._save_post_btn.text()

    def test_has_cancel_button(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton

        form = _make_cn_form(qapp)
        assert isinstance(form._cancel_btn, QPushButton)
        assert form._cancel_btn.text() == "Cancel"

    def test_cancel_emits_signal(self, qapp) -> None:
        form = _make_cn_form(qapp)
        received = []
        form.cancelled.connect(lambda: received.append(True))
        form._cancel_btn.click()
        assert received == [True]


class TestCreditNoteFormContactCombo:
    def test_contact_combo_has_contacts(self, qapp) -> None:
        form = _make_cn_form(qapp)
        # 1 placeholder + 1 contact
        assert form._contact_combo.count() == 2

    def test_contact_combo_first_item_is_placeholder(self, qapp) -> None:
        form = _make_cn_form(qapp)
        assert "Select" in form._contact_combo.itemText(0)

    def test_contact_combo_second_item_is_contact(self, qapp) -> None:
        form = _make_cn_form(qapp)
        assert form._contact_combo.itemText(1) == "Acme Corp"


class TestCreditNoteFormValidation:
    def test_no_contact_shows_banner(self, qapp) -> None:
        form = _make_cn_form(qapp)
        # Contact is at index 0 (placeholder)
        form._contact_combo.setCurrentIndex(0)
        result = form._build_payload("draft")
        assert result is None
        assert not form._banner.isHidden()

    def test_with_contact_returns_payload(self, qapp) -> None:
        form = _make_cn_form(qapp)
        form._contact_combo.setCurrentIndex(1)  # Acme Corp
        result = form._build_payload("draft")
        assert result is not None
        assert result["contact_id"] == _UUID_CONTACT

    def test_payload_contains_date(self, qapp) -> None:
        form = _make_cn_form(qapp)
        form._contact_combo.setCurrentIndex(1)
        result = form._build_payload("draft")
        assert "date" in result

    def test_payload_contains_lines(self, qapp) -> None:
        form = _make_cn_form(qapp)
        form._contact_combo.setCurrentIndex(1)
        result = form._build_payload("draft")
        assert isinstance(result["lines"], list)
        assert len(result["lines"]) == 1


class TestCreditNoteFormAddRemoveLine:
    def test_add_line_increments_count(self, qapp) -> None:
        form = _make_cn_form(qapp)
        assert form.line_count() == 1
        form._on_add_line()
        assert form.line_count() == 2

    def test_remove_line_decrements_count(self, qapp) -> None:
        form = _make_cn_form(qapp)
        form._on_add_line()
        assert form.line_count() == 2
        form._on_remove_line(1)
        assert form.line_count() == 1

    def test_cannot_remove_last_line(self, qapp) -> None:
        form = _make_cn_form(qapp)
        assert form.line_count() == 1
        form._on_remove_line(0)
        assert form.line_count() == 1  # still 1


class TestCreditNoteFormSaveCreate:
    def test_save_draft_emits_credit_note_saved(self, qapp) -> None:
        form = _make_cn_form(qapp)
        form._contact_combo.setCurrentIndex(1)

        received: list[str] = []
        form.credit_note_saved.connect(received.append)

        with patch(_PATCH_CREATE, return_value={"id": "cn-new", "version": 1}):
            form._on_save_draft()

        assert received == ["cn-new"]

    def test_save_post_creates_then_posts(self, qapp) -> None:
        form = _make_cn_form(qapp)
        form._contact_combo.setCurrentIndex(1)

        received: list[str] = []
        form.credit_note_saved.connect(received.append)

        with (
            patch(_PATCH_CREATE, return_value={"id": "cn-new", "version": 1}),
            patch(_PATCH_POST, return_value={"id": "cn-new", "status": "posted"}) as mock_post,
        ):
            form._on_save_post()

        assert received == ["cn-new"]
        mock_post.assert_called_once()


class TestCreditNoteFormEditMode:
    def test_loads_existing_data_into_form(self, qapp) -> None:
        form = _make_cn_form(qapp, credit_note_id="cn-001", existing_data=_SAMPLE_CN_DETAIL)
        # The contact combo should be set to the existing contact
        assert form._contact_combo.currentData() == _UUID_CONTACT

    def test_loads_existing_lines(self, qapp) -> None:
        form = _make_cn_form(qapp, credit_note_id="cn-001", existing_data=_SAMPLE_CN_DETAIL)
        assert form.line_count() == 1

    def test_update_on_save_draft(self, qapp) -> None:
        form = _make_cn_form(qapp, credit_note_id="cn-001", existing_data=_SAMPLE_CN_DETAIL)
        received: list[str] = []
        form.credit_note_saved.connect(received.append)

        with patch(
            _PATCH_UPDATE,
            return_value=(200, {"id": "cn-001", "version": 2}),
        ):
            form._on_save_draft()

        assert received == ["cn-001"]

    def test_version_conflict_shows_banner(self, qapp) -> None:
        form = _make_cn_form(qapp, credit_note_id="cn-001", existing_data=_SAMPLE_CN_DETAIL)

        with patch(
            _PATCH_UPDATE,
            return_value=(409, {"detail": "conflict"}),
        ):
            form._on_save_draft()

        assert not form._banner.isHidden()
