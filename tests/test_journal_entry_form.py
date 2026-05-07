"""Tests for JournalEntryForm — offscreen Qt, mocked API service layer.

All HTTP calls are patched at the module-level import point inside the
service layer so no real server is needed.
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

_UUID_ACCOUNT_CASH = "a0000000-0000-0000-0000-000000000001"
_UUID_ACCOUNT_REVENUE = "a0000000-0000-0000-0000-000000000002"

_SAMPLE_ACCOUNTS = [
    {"id": _UUID_ACCOUNT_CASH, "name": "Cash at Bank"},
    {"id": _UUID_ACCOUNT_REVENUE, "name": "Sales Revenue"},
]

_SAMPLE_JE = {
    "id": "je-001",
    "entry_date": "2024-03-01",
    "reference": "JE-001",
    "narration": "Test journal entry",
    "version": 1,
    "lines": [
        {
            "account_id": _UUID_ACCOUNT_CASH,
            "description": "Cash receipt",
            "debit": "500.00",
            "credit": "0.00",
        },
        {
            "account_id": _UUID_ACCOUNT_REVENUE,
            "description": "Revenue recognised",
            "debit": "0.00",
            "credit": "500.00",
        },
    ],
}


# ---------------------------------------------------------------------------
# Patch targets
# ---------------------------------------------------------------------------

_PATCH_LIST_ACCOUNTS = "saebooks_desktop.views.journal_entry_form.list_all_accounts"
_PATCH_CREATE = "saebooks_desktop.views.journal_entry_form.create_journal_entry"
_PATCH_UPDATE = "saebooks_desktop.views.journal_entry_form.update_journal_entry"
_PATCH_POST = "saebooks_desktop.views.journal_entry_form.post_journal_entry"


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_client():
    return MagicMock()


def _make_form_create(qapp, accounts=None):
    """Return a blank JournalEntryForm (create mode)."""
    from saebooks_desktop.views.journal_entry_form import JournalEntryForm

    with patch(_PATCH_LIST_ACCOUNTS, return_value=accounts or _SAMPLE_ACCOUNTS):
        form = JournalEntryForm(_make_client())
    return form


def _make_form_edit(qapp, je_data=None, accounts=None):
    """Return a JournalEntryForm in edit mode pre-filled from je_data."""
    from saebooks_desktop.views.journal_entry_form import JournalEntryForm

    data = je_data if je_data is not None else _SAMPLE_JE
    client = _make_client()
    client.get.return_value = data

    with patch(_PATCH_LIST_ACCOUNTS, return_value=accounts or _SAMPLE_ACCOUNTS):
        form = JournalEntryForm(client, je_id=data["id"])
    return form


# ---------------------------------------------------------------------------
# Instantiation tests
# ---------------------------------------------------------------------------


class TestJournalEntryFormCreate:
    def test_instantiates_without_crash(self, qapp) -> None:
        form = _make_form_create(qapp)
        assert form is not None

    def test_date_defaults_to_today(self, qapp) -> None:
        from PySide6.QtCore import QDate

        form = _make_form_create(qapp)
        assert form._date_edit.date() == QDate.currentDate()

    def test_reference_edit_starts_empty(self, qapp) -> None:
        form = _make_form_create(qapp)
        assert form._reference_edit.text() == ""

    def test_narration_edit_starts_empty(self, qapp) -> None:
        form = _make_form_create(qapp)
        assert form._narration_edit.text() == ""

    def test_starts_with_two_lines(self, qapp) -> None:
        """Journal entries require at least one Dr and one Cr row."""
        form = _make_form_create(qapp)
        assert form.line_count() == 2

    def test_has_save_draft_button(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton

        form = _make_form_create(qapp)
        assert isinstance(form._save_draft_btn, QPushButton)

    def test_has_save_post_button(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton

        form = _make_form_create(qapp)
        assert isinstance(form._save_post_btn, QPushButton)

    def test_has_cancel_button(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton

        form = _make_form_create(qapp)
        assert isinstance(form._cancel_btn, QPushButton)

    def test_save_buttons_disabled_when_unbalanced(self, qapp) -> None:
        """Fresh form has all zeros so Dr==Cr==0, balanced — but once we set a
        single debit > 0 without a matching credit the buttons must disable."""
        form = _make_form_create(qapp)
        debit_w = form._lines_table.cellWidget(0, 2)
        debit_w.setValue(100.0)
        # Now Dr=100, Cr=0 → unbalanced
        assert not form._save_draft_btn.isEnabled()
        assert not form._save_post_btn.isEnabled()

    def test_save_buttons_enabled_when_balanced(self, qapp) -> None:
        form = _make_form_create(qapp)
        debit_w = form._lines_table.cellWidget(0, 2)
        credit_w = form._lines_table.cellWidget(1, 3)
        debit_w.setValue(200.0)
        credit_w.setValue(200.0)
        assert form._save_draft_btn.isEnabled()
        assert form._save_post_btn.isEnabled()

    def test_account_combo_has_placeholder(self, qapp) -> None:
        form = _make_form_create(qapp)
        acc_w = form._lines_table.cellWidget(0, 0)
        assert acc_w is not None
        assert acc_w.itemText(0) == "-- Account --"

    def test_account_combo_populated_from_accounts(self, qapp) -> None:
        form = _make_form_create(qapp)
        acc_w = form._lines_table.cellWidget(0, 0)
        # placeholder + 2 accounts
        assert acc_w.count() == 3


# ---------------------------------------------------------------------------
# Edit mode — pre-fill
# ---------------------------------------------------------------------------


class TestJournalEntryFormEdit:
    def test_edit_mode_prefills_date(self, qapp) -> None:
        from PySide6.QtCore import QDate

        form = _make_form_edit(qapp)
        assert form._date_edit.date() == QDate.fromString("2024-03-01", "yyyy-MM-dd")

    def test_edit_mode_prefills_reference(self, qapp) -> None:
        form = _make_form_edit(qapp)
        assert form._reference_edit.text() == "JE-001"

    def test_edit_mode_prefills_narration(self, qapp) -> None:
        form = _make_form_edit(qapp)
        assert form._narration_edit.text() == "Test journal entry"

    def test_edit_mode_loads_two_lines(self, qapp) -> None:
        form = _make_form_edit(qapp)
        assert form.line_count() == 2

    def test_edit_mode_prefills_description_line0(self, qapp) -> None:
        form = _make_form_edit(qapp)
        desc_w = form._lines_table.cellWidget(0, 1)
        assert desc_w is not None
        assert desc_w.text() == "Cash receipt"

    def test_edit_mode_prefills_debit_line0(self, qapp) -> None:
        form = _make_form_edit(qapp)
        debit_w = form._lines_table.cellWidget(0, 2)
        assert debit_w is not None
        assert debit_w.value() == pytest.approx(500.0)

    def test_edit_mode_prefills_credit_line1(self, qapp) -> None:
        form = _make_form_edit(qapp)
        credit_w = form._lines_table.cellWidget(1, 3)
        assert credit_w is not None
        assert credit_w.value() == pytest.approx(500.0)

    def test_edit_mode_stores_etag(self, qapp) -> None:
        form = _make_form_edit(qapp)
        assert form._etag == 1

    def test_edit_mode_is_balanced(self, qapp) -> None:
        form = _make_form_edit(qapp)
        assert form.is_balanced()


# ---------------------------------------------------------------------------
# Line item interactions
# ---------------------------------------------------------------------------


class TestJournalEntryFormLineItems:
    def test_add_line_appends_row(self, qapp) -> None:
        form = _make_form_create(qapp)
        assert form.line_count() == 2
        form._on_add_line()
        assert form.line_count() == 3

    def test_add_line_three_times(self, qapp) -> None:
        form = _make_form_create(qapp)
        form._on_add_line()
        form._on_add_line()
        form._on_add_line()
        assert form.line_count() == 5

    def test_remove_line_removes_row(self, qapp) -> None:
        form = _make_form_create(qapp)
        form._on_add_line()
        assert form.line_count() == 3
        form._on_remove_line(2)
        assert form.line_count() == 2

    def test_remove_enforces_minimum_two_lines(self, qapp) -> None:
        """Cannot remove below _MIN_LINES (2)."""
        form = _make_form_create(qapp)
        assert form.line_count() == 2
        form._on_remove_line(0)
        assert form.line_count() == 2

    def test_remove_still_enforces_minimum_after_add(self, qapp) -> None:
        form = _make_form_create(qapp)
        form._on_add_line()  # 3 lines
        form._on_remove_line(0)  # 2 lines
        form._on_remove_line(0)  # still 2 — blocked
        assert form.line_count() == 2


# ---------------------------------------------------------------------------
# Dr/Cr mutual exclusion
# ---------------------------------------------------------------------------


class TestDrCrMutualExclusion:
    def test_setting_debit_clears_credit(self, qapp) -> None:
        form = _make_form_create(qapp)
        credit_w = form._lines_table.cellWidget(0, 3)
        debit_w = form._lines_table.cellWidget(0, 2)
        credit_w.setValue(50.0)
        debit_w.setValue(100.0)
        assert credit_w.value() == pytest.approx(0.0)

    def test_setting_credit_clears_debit(self, qapp) -> None:
        form = _make_form_create(qapp)
        debit_w = form._lines_table.cellWidget(0, 2)
        credit_w = form._lines_table.cellWidget(0, 3)
        debit_w.setValue(75.0)
        credit_w.setValue(75.0)
        assert debit_w.value() == pytest.approx(0.0)

    def test_setting_debit_zero_does_not_clear_credit(self, qapp) -> None:
        """Setting debit back to zero should NOT clear credit."""
        form = _make_form_create(qapp)
        credit_w = form._lines_table.cellWidget(0, 3)
        debit_w = form._lines_table.cellWidget(0, 2)
        credit_w.setValue(50.0)
        debit_w.setValue(0.0)
        assert credit_w.value() == pytest.approx(50.0)

    def test_mutual_exclusion_on_second_row(self, qapp) -> None:
        form = _make_form_create(qapp)
        debit_w = form._lines_table.cellWidget(1, 2)
        credit_w = form._lines_table.cellWidget(1, 3)
        credit_w.setValue(200.0)
        debit_w.setValue(200.0)
        assert credit_w.value() == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Totals
# ---------------------------------------------------------------------------


class TestJournalEntryFormTotals:
    def test_totals_start_at_zero(self, qapp) -> None:
        form = _make_form_create(qapp)
        assert form._dr_total_label.text() == "0.00"
        assert form._cr_total_label.text() == "0.00"
        assert form._diff_label.text() == "0.00"

    def test_debit_total_correct(self, qapp) -> None:
        form = _make_form_create(qapp)
        debit_w0 = form._lines_table.cellWidget(0, 2)
        debit_w1 = form._lines_table.cellWidget(1, 2)
        debit_w0.setValue(300.0)
        debit_w1.setValue(200.0)
        form._recalculate_totals()
        assert form._dr_total_label.text() == "500.00"

    def test_credit_total_correct(self, qapp) -> None:
        form = _make_form_create(qapp)
        credit_w = form._lines_table.cellWidget(1, 3)
        credit_w.setValue(750.0)
        form._recalculate_totals()
        assert form._cr_total_label.text() == "750.00"

    def test_difference_shows_imbalance(self, qapp) -> None:
        form = _make_form_create(qapp)
        debit_w = form._lines_table.cellWidget(0, 2)
        debit_w.setValue(100.0)
        form._recalculate_totals()
        assert form._diff_label.text() == "100.00"

    def test_difference_zero_when_balanced(self, qapp) -> None:
        form = _make_form_create(qapp)
        debit_w = form._lines_table.cellWidget(0, 2)
        credit_w = form._lines_table.cellWidget(1, 3)
        debit_w.setValue(400.0)
        credit_w.setValue(400.0)
        form._recalculate_totals()
        assert form._diff_label.text() == "0.00"

    def test_diff_label_red_when_imbalanced(self, qapp) -> None:
        form = _make_form_create(qapp)
        debit_w = form._lines_table.cellWidget(0, 2)
        debit_w.setValue(50.0)
        form._recalculate_totals()
        assert "#c62828" in form._diff_label.styleSheet()


# ---------------------------------------------------------------------------
# Save as Draft
# ---------------------------------------------------------------------------


class TestJournalEntryFormSaveDraft:
    def _balance_form(self, form) -> None:
        """Set row 0 debit=100, row 1 credit=100."""
        debit_w = form._lines_table.cellWidget(0, 2)
        credit_w = form._lines_table.cellWidget(1, 3)
        debit_w.setValue(100.0)
        credit_w.setValue(100.0)

    def test_save_draft_calls_create(self, qapp) -> None:
        form = _make_form_create(qapp)
        self._balance_form(form)

        mock_result = {"id": "je-new", "version": 1}
        with patch(_PATCH_CREATE, return_value=mock_result) as mock_create:
            form._on_save_draft()

        mock_create.assert_called_once()

    def test_save_draft_payload_has_entry_date(self, qapp) -> None:
        from PySide6.QtCore import QDate

        form = _make_form_create(qapp)
        self._balance_form(form)

        today_str = QDate.currentDate().toString("yyyy-MM-dd")
        with patch(_PATCH_CREATE, return_value={"id": "je-new", "version": 1}) as mock_create:
            form._on_save_draft()

        payload = mock_create.call_args[0][1]
        assert payload["entry_date"] == today_str

    def test_save_draft_emits_journal_saved(self, qapp) -> None:
        form = _make_form_create(qapp)
        self._balance_form(form)

        received: list[str] = []
        form.journal_saved.connect(received.append)

        with patch(_PATCH_CREATE, return_value={"id": "je-new", "version": 1}):
            form._on_save_draft()

        assert received == ["je-new"]

    def test_save_draft_blocked_when_unbalanced(self, qapp) -> None:
        form = _make_form_create(qapp)
        debit_w = form._lines_table.cellWidget(0, 2)
        debit_w.setValue(100.0)
        # credit still 0 — unbalanced

        received: list[str] = []
        form.journal_saved.connect(received.append)
        with patch(_PATCH_CREATE) as mock_create:
            form._on_save_draft()

        mock_create.assert_not_called()
        assert received == []

    def test_save_draft_shows_banner_on_api_error(self, qapp) -> None:
        form = _make_form_create(qapp)
        self._balance_form(form)

        with patch(_PATCH_CREATE, side_effect=RuntimeError("network error")):
            form._on_save_draft()

        assert not form._banner.isHidden()
        assert "save failed" in form._banner.text().lower()


# ---------------------------------------------------------------------------
# Save & Post
# ---------------------------------------------------------------------------


class TestJournalEntryFormSavePost:
    def _balance_form(self, form) -> None:
        debit_w = form._lines_table.cellWidget(0, 2)
        credit_w = form._lines_table.cellWidget(1, 3)
        debit_w.setValue(250.0)
        credit_w.setValue(250.0)

    def test_save_post_calls_create_then_post(self, qapp) -> None:
        form = _make_form_create(qapp)
        self._balance_form(form)

        mock_result = {"id": "je-posted", "version": 2}
        with (
            patch(_PATCH_CREATE, return_value=mock_result) as mock_create,
            patch(_PATCH_POST, return_value={"id": "je-posted", "status": "posted"}) as mock_post,
        ):
            form._on_save_post()

        mock_create.assert_called_once()
        mock_post.assert_called_once()
        assert mock_post.call_args[0][1] == "je-posted"

    def test_save_post_emits_journal_saved(self, qapp) -> None:
        form = _make_form_create(qapp)
        self._balance_form(form)

        received: list[str] = []
        form.journal_saved.connect(received.append)

        with (
            patch(_PATCH_CREATE, return_value={"id": "je-posted", "version": 2}),
            patch(_PATCH_POST, return_value={}),
        ):
            form._on_save_post()

        assert received == ["je-posted"]


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


class TestJournalEntryFormCancel:
    def test_cancel_emits_cancelled_signal(self, qapp) -> None:
        form = _make_form_create(qapp)
        received = []
        form.cancelled.connect(lambda: received.append(True))
        form._cancel_btn.click()
        assert received == [True]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestJournalEntryFormValidation:
    def test_build_payload_fails_when_unbalanced(self, qapp) -> None:
        form = _make_form_create(qapp)
        debit_w = form._lines_table.cellWidget(0, 2)
        debit_w.setValue(100.0)
        result = form._build_payload()
        assert result is None
        assert not form._banner.isHidden()

    def test_build_payload_succeeds_when_balanced(self, qapp) -> None:
        form = _make_form_create(qapp)
        debit_w = form._lines_table.cellWidget(0, 2)
        credit_w = form._lines_table.cellWidget(1, 3)
        debit_w.setValue(100.0)
        credit_w.setValue(100.0)
        result = form._build_payload()
        assert result is not None
        assert "entry_date" in result
        assert "lines" in result

    def test_build_payload_includes_narration_when_set(self, qapp) -> None:
        form = _make_form_create(qapp)
        form._narration_edit.setText("Salary accrual")
        debit_w = form._lines_table.cellWidget(0, 2)
        credit_w = form._lines_table.cellWidget(1, 3)
        debit_w.setValue(100.0)
        credit_w.setValue(100.0)
        result = form._build_payload()
        assert result is not None
        assert result.get("narration") == "Salary accrual"

    def test_build_payload_omits_narration_when_empty(self, qapp) -> None:
        form = _make_form_create(qapp)
        debit_w = form._lines_table.cellWidget(0, 2)
        credit_w = form._lines_table.cellWidget(1, 3)
        debit_w.setValue(100.0)
        credit_w.setValue(100.0)
        result = form._build_payload()
        assert result is not None
        assert "narration" not in result

    def test_build_payload_lines_have_debit_credit_keys(self, qapp) -> None:
        form = _make_form_create(qapp)
        debit_w = form._lines_table.cellWidget(0, 2)
        credit_w = form._lines_table.cellWidget(1, 3)
        debit_w.setValue(50.0)
        credit_w.setValue(50.0)
        result = form._build_payload()
        assert result is not None
        for line in result["lines"]:
            assert "debit" in line
            assert "credit" in line


# ---------------------------------------------------------------------------
# Etag handling on update
# ---------------------------------------------------------------------------


class TestJournalEntryFormEtag:
    def _balance_form(self, form) -> None:
        debit_w = form._lines_table.cellWidget(0, 2)
        credit_w = form._lines_table.cellWidget(1, 3)
        debit_w.setValue(500.0)
        credit_w.setValue(500.0)

    def test_update_sends_etag(self, qapp) -> None:
        form = _make_form_edit(qapp)
        self._balance_form(form)

        mock_result = (200, {"id": "je-001", "version": 2})
        with patch(_PATCH_UPDATE, return_value=mock_result) as mock_update:
            form._on_save_draft()

        mock_update.assert_called_once()
        assert mock_update.call_args[0][3] == 1  # version from _SAMPLE_JE

    def test_update_conflict_shows_banner(self, qapp) -> None:
        form = _make_form_edit(qapp)
        self._balance_form(form)

        mock_result = (409, {"detail": "version mismatch"})
        received: list[str] = []
        form.journal_saved.connect(received.append)

        with patch(_PATCH_UPDATE, return_value=mock_result):
            form._on_save_draft()

        assert received == []
        assert not form._banner.isHidden()
        assert "conflict" in form._banner.text().lower()
