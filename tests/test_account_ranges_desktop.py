"""Tests for AccountRangesView and CreateAccountRangeDialog.

All tests run without a real API server.  The service function
``saebooks_desktop.services.account_ranges.list_account_ranges`` is patched
at the module-level import point inside the view so no HTTP calls are made.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_PATCH_LIST = "saebooks_desktop.views.account_ranges.list_account_ranges"
_PATCH_CREATE = "saebooks_desktop.views.account_ranges.create_account_range"


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


_SAMPLE_RANGES = [
    {
        "id": "ar-001",
        "name": "Current Assets",
        "range_type": "ASSET",
        "from_code": "1000",
        "to_code": "1999",
    },
    {
        "id": "ar-002",
        "name": "Current Liabilities",
        "range_type": "LIABILITY",
        "from_code": "2000",
        "to_code": "2999",
    },
    {
        "id": "ar-003",
        "name": "Revenue",
        "range_type": "INCOME",
        "from_code": "4000",
        "to_code": "4999",
    },
]


def _make_view(qapp, items=None, side_effect=None):
    from saebooks_desktop.views.account_ranges import AccountRangesView

    if side_effect is not None:
        with patch(_PATCH_LIST, side_effect=side_effect):
            return AccountRangesView()
    else:
        with patch(_PATCH_LIST, return_value=items if items is not None else []):
            return AccountRangesView()


class TestAccountRangesViewInstantiation:
    def test_instantiates_without_crash(self, qapp) -> None:
        view = _make_view(qapp, items=[])
        assert view is not None

    def test_has_table_model(self, qapp) -> None:
        from PySide6.QtGui import QStandardItemModel

        view = _make_view(qapp, items=[])
        assert isinstance(view._model, QStandardItemModel)

    def test_has_four_columns(self, qapp) -> None:
        view = _make_view(qapp, items=[])
        assert view._model.columnCount() == 4

    def test_column_headers(self, qapp) -> None:
        expected = ["Name", "Type", "From Code", "To Code"]
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
        assert view._new_btn.text() == "New Account Range"


class TestAccountRangesViewModelPopulation:
    def test_row_count_matches_items(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_RANGES)
        assert view._model.rowCount() == 3

    def test_name_column(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_RANGES)
        assert view._model.item(0, 0).text() == "Current Assets"
        assert view._model.item(1, 0).text() == "Current Liabilities"

    def test_type_column(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_RANGES)
        assert view._model.item(0, 1).text() == "ASSET"
        assert view._model.item(1, 1).text() == "LIABILITY"

    def test_from_code_column(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_RANGES)
        assert view._model.item(0, 2).text() == "1000"

    def test_to_code_column(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_RANGES)
        assert view._model.item(0, 3).text() == "1999"

    def test_id_stored_as_user_role(self, qapp) -> None:
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_RANGES)
        stored_id = view._model.item(0, 0).data(Qt.ItemDataRole.UserRole)
        assert stored_id == "ar-001"

    def test_empty_state_zero_rows(self, qapp) -> None:
        view = _make_view(qapp, items=[])
        assert view._model.rowCount() == 0


class TestAccountRangesViewOffline:
    def test_offline_banner_shown_on_error(self, qapp) -> None:
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _make_view(qapp, side_effect=ServerOfflineError("offline"))
        assert not view._offline_label.isHidden()

    def test_offline_banner_hidden_when_data_loads(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_RANGES)
        assert view._offline_label.isHidden()


class TestAccountRangesViewDoubleClick:
    def test_double_click_emits_range_selected(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_RANGES)
        received: list[str] = []
        view.range_selected.connect(received.append)
        index = view._model.index(0, 0)
        view._on_double_click(index)
        assert received == ["ar-001"]

    def test_double_click_second_row(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_RANGES)
        received: list[str] = []
        view.range_selected.connect(received.append)
        index = view._model.index(1, 0)
        view._on_double_click(index)
        assert received == ["ar-002"]


class TestAccountRangesReload:
    def test_reload_replaces_rows(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_RANGES)
        assert view._model.rowCount() == 3
        with patch(_PATCH_LIST, return_value=[_SAMPLE_RANGES[0]]):
            view.reload()
        assert view._model.rowCount() == 1


class TestCreateAccountRangeDialog:
    def test_dialog_instantiates(self, qapp) -> None:
        from saebooks_desktop.views.account_ranges import CreateAccountRangeDialog

        dlg = CreateAccountRangeDialog()
        assert dlg is not None

    def test_dialog_has_type_combo(self, qapp) -> None:
        from PySide6.QtWidgets import QComboBox

        from saebooks_desktop.views.account_ranges import CreateAccountRangeDialog

        dlg = CreateAccountRangeDialog()
        assert isinstance(dlg._type_combo, QComboBox)

    def test_dialog_type_combo_contains_asset(self, qapp) -> None:
        from saebooks_desktop.views.account_ranges import CreateAccountRangeDialog

        dlg = CreateAccountRangeDialog()
        options = [dlg._type_combo.itemText(i) for i in range(dlg._type_combo.count())]
        assert "ASSET" in options
        assert "LIABILITY" in options
        assert "INCOME" in options
        assert "EXPENSE" in options

    def test_current_data_returns_form_values(self, qapp) -> None:
        from saebooks_desktop.views.account_ranges import CreateAccountRangeDialog

        dlg = CreateAccountRangeDialog()
        dlg._name_edit.setText("Non-Current Assets")
        dlg._from_edit.setText("1500")
        dlg._to_edit.setText("1599")
        data = dlg.current_data()
        assert data["name"] == "Non-Current Assets"
        assert data["from_code"] == "1500"
        assert data["to_code"] == "1599"
