"""Tests for JournalTemplatesView and CreateJournalTemplateDialog.

All tests run without a real API server.  Service functions are patched at
their import points inside the view so no HTTP calls are made.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_PATCH_LIST = "saebooks_desktop.views.journal_templates.list_journal_templates"
_PATCH_CREATE = "saebooks_desktop.views.journal_templates.create_journal_template"


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


_SAMPLE_TEMPLATES = [
    {
        "id": "jt-001",
        "name": "Monthly Depreciation",
        "description": "Standard monthly depreciation entry",
        "lines": [{"id": "l1"}, {"id": "l2"}],
    },
    {
        "id": "jt-002",
        "name": "Accrual Reversal",
        "description": "Reverse prior month accruals",
        "lines": [],
    },
    {
        "id": "jt-003",
        "name": "Prepaid Expense",
        "description": "Prepaid amortisation",
        "line_count": 4,
    },
]


def _make_view(qapp, items=None, side_effect=None):
    from saebooks_desktop.views.journal_templates import JournalTemplatesView

    if side_effect is not None:
        with patch(_PATCH_LIST, side_effect=side_effect):
            return JournalTemplatesView()
    else:
        with patch(_PATCH_LIST, return_value=items if items is not None else []):
            return JournalTemplatesView()


class TestJournalTemplatesViewInstantiation:
    def test_instantiates_without_crash(self, qapp) -> None:
        view = _make_view(qapp, items=[])
        assert view is not None

    def test_has_table_model(self, qapp) -> None:
        from PySide6.QtGui import QStandardItemModel

        view = _make_view(qapp, items=[])
        assert isinstance(view._model, QStandardItemModel)

    def test_has_three_columns(self, qapp) -> None:
        view = _make_view(qapp, items=[])
        assert view._model.columnCount() == 3

    def test_column_headers(self, qapp) -> None:
        expected = ["Name", "Description", "Line Count"]
        view = _make_view(qapp, items=[])
        headers = [
            view._model.horizontalHeaderItem(i).text()
            for i in range(view._model.columnCount())
        ]
        assert headers == expected

    def test_has_new_button(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton

        view = _make_view(qapp, items=[])
        assert isinstance(view._new_btn, QPushButton)
        assert view._new_btn.text() == "New Template"


class TestJournalTemplatesViewModelPopulation:
    def test_row_count_matches_items(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_TEMPLATES)
        assert view._model.rowCount() == 3

    def test_name_column(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_TEMPLATES)
        assert view._model.item(0, 0).text() == "Monthly Depreciation"

    def test_description_column(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_TEMPLATES)
        assert view._model.item(0, 1).text() == "Standard monthly depreciation entry"

    def test_line_count_from_lines_list(self, qapp) -> None:
        """Line count is derived from the len(lines) list when present."""
        view = _make_view(qapp, items=_SAMPLE_TEMPLATES)
        assert view._model.item(0, 2).text() == "2"  # jt-001 has 2 lines
        assert view._model.item(1, 2).text() == "0"  # jt-002 has empty lines

    def test_line_count_from_line_count_key(self, qapp) -> None:
        """Falls back to line_count key if lines list absent."""
        view = _make_view(qapp, items=_SAMPLE_TEMPLATES)
        assert view._model.item(2, 2).text() == "4"  # jt-003 uses line_count

    def test_line_count_right_aligned(self, qapp) -> None:
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_TEMPLATES)
        item = view._model.item(0, 2)
        assert item.textAlignment() & Qt.AlignmentFlag.AlignRight

    def test_id_stored_as_user_role(self, qapp) -> None:
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_TEMPLATES)
        stored_id = view._model.item(0, 0).data(Qt.ItemDataRole.UserRole)
        assert stored_id == "jt-001"

    def test_empty_state_zero_rows(self, qapp) -> None:
        view = _make_view(qapp, items=[])
        assert view._model.rowCount() == 0


class TestJournalTemplatesViewOffline:
    def test_offline_banner_shown_on_error(self, qapp) -> None:
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _make_view(qapp, side_effect=ServerOfflineError("offline"))
        assert not view._offline_label.isHidden()

    def test_offline_banner_hidden_when_data_loads(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_TEMPLATES)
        assert view._offline_label.isHidden()


class TestJournalTemplatesViewDoubleClick:
    def test_double_click_emits_template_selected(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_TEMPLATES)
        received: list[str] = []
        view.template_selected.connect(received.append)
        index = view._model.index(0, 0)
        view._on_double_click(index)
        assert received == ["jt-001"]

    def test_double_click_second_row(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_TEMPLATES)
        received: list[str] = []
        view.template_selected.connect(received.append)
        index = view._model.index(2, 0)
        view._on_double_click(index)
        assert received == ["jt-003"]


class TestJournalTemplatesReload:
    def test_reload_replaces_rows(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_TEMPLATES)
        assert view._model.rowCount() == 3
        with patch(_PATCH_LIST, return_value=[_SAMPLE_TEMPLATES[0]]):
            view.reload()
        assert view._model.rowCount() == 1


class TestCreateJournalTemplateDialog:
    def test_dialog_instantiates(self, qapp) -> None:
        from saebooks_desktop.views.journal_templates import CreateJournalTemplateDialog

        dlg = CreateJournalTemplateDialog()
        assert dlg is not None

    def test_has_name_field(self, qapp) -> None:
        from PySide6.QtWidgets import QLineEdit

        from saebooks_desktop.views.journal_templates import CreateJournalTemplateDialog

        dlg = CreateJournalTemplateDialog()
        assert isinstance(dlg._name_edit, QLineEdit)

    def test_has_description_field(self, qapp) -> None:
        from PySide6.QtWidgets import QLineEdit

        from saebooks_desktop.views.journal_templates import CreateJournalTemplateDialog

        dlg = CreateJournalTemplateDialog()
        assert isinstance(dlg._desc_edit, QLineEdit)

    def test_current_data_returns_form_values(self, qapp) -> None:
        from saebooks_desktop.views.journal_templates import CreateJournalTemplateDialog

        dlg = CreateJournalTemplateDialog()
        dlg._name_edit.setText("Year End Close")
        dlg._desc_edit.setText("Close all income and expense accounts")
        data = dlg.current_data()
        assert data["name"] == "Year End Close"
        assert data["description"] == "Close all income and expense accounts"
