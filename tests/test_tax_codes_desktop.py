"""Tests for TaxCodesView and TaxCodeDialog.

All tests run without a real API server.  Service functions are patched at
their import points inside the view so no HTTP calls are made.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_PATCH_LIST = "saebooks_desktop.views.tax_codes.list_tax_codes"
_PATCH_CREATE = "saebooks_desktop.views.tax_codes.create_tax_code"


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


_SAMPLE_CODES = [
    {
        "id": "tc-001",
        "code": "GST",
        "name": "Goods and Services Tax",
        "rate": 10.0,
        "tax_type": "GST",
    },
    {
        "id": "tc-002",
        "code": "FRE",
        "name": "GST Free",
        "rate": 0.0,
        "tax_type": "FRE",
    },
    {
        "id": "tc-003",
        "code": "INP",
        "name": "Input Tax Credit",
        "rate": 10.0,
        "tax_type": "INP",
    },
]


def _make_view(qapp, items=None, side_effect=None):
    from saebooks_desktop.views.tax_codes import TaxCodesView

    if side_effect is not None:
        with patch(_PATCH_LIST, side_effect=side_effect):
            return TaxCodesView()
    else:
        with patch(_PATCH_LIST, return_value=items if items is not None else []):
            return TaxCodesView()


class TestTaxCodesViewInstantiation:
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
        expected = ["Code", "Name", "Rate (%)", "Type"]
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
        assert view._new_btn.text() == "New Tax Code"


class TestTaxCodesViewModelPopulation:
    def test_row_count_matches_items(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_CODES)
        assert view._model.rowCount() == 3

    def test_code_column(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_CODES)
        assert view._model.item(0, 0).text() == "GST"
        assert view._model.item(1, 0).text() == "FRE"

    def test_name_column(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_CODES)
        assert view._model.item(0, 1).text() == "Goods and Services Tax"

    def test_rate_column(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_CODES)
        assert view._model.item(0, 2).text() == "10.0"
        assert view._model.item(1, 2).text() == "0.0"

    def test_rate_right_aligned(self, qapp) -> None:
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_CODES)
        item = view._model.item(0, 2)
        assert item.textAlignment() & Qt.AlignmentFlag.AlignRight

    def test_type_column(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_CODES)
        assert view._model.item(0, 3).text() == "GST"
        assert view._model.item(1, 3).text() == "FRE"

    def test_id_stored_as_user_role(self, qapp) -> None:
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_CODES)
        stored_id = view._model.item(0, 0).data(Qt.ItemDataRole.UserRole)
        assert stored_id == "tc-001"

    def test_empty_state_zero_rows(self, qapp) -> None:
        view = _make_view(qapp, items=[])
        assert view._model.rowCount() == 0


class TestTaxCodesViewOffline:
    def test_offline_banner_shown_on_error(self, qapp) -> None:
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _make_view(qapp, side_effect=ServerOfflineError("offline"))
        assert not view._offline_label.isHidden()

    def test_offline_banner_hidden_when_data_loads(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_CODES)
        assert view._offline_label.isHidden()


class TestTaxCodesViewDoubleClick:
    def test_double_click_emits_code_selected(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_CODES)
        received: list[str] = []
        view.code_selected.connect(received.append)
        index = view._model.index(0, 0)
        view._on_double_click(index)
        assert received == ["tc-001"]

    def test_double_click_second_row(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_CODES)
        received: list[str] = []
        view.code_selected.connect(received.append)
        index = view._model.index(2, 0)
        view._on_double_click(index)
        assert received == ["tc-003"]


class TestTaxCodesReload:
    def test_reload_replaces_rows(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_CODES)
        assert view._model.rowCount() == 3
        with patch(_PATCH_LIST, return_value=[_SAMPLE_CODES[0]]):
            view.reload()
        assert view._model.rowCount() == 1


class TestTaxCodeDialog:
    def test_dialog_instantiates_for_create(self, qapp) -> None:
        from saebooks_desktop.views.tax_codes import TaxCodeDialog

        dlg = TaxCodeDialog()
        assert dlg is not None

    def test_dialog_title_new(self, qapp) -> None:
        from saebooks_desktop.views.tax_codes import TaxCodeDialog

        dlg = TaxCodeDialog()
        assert dlg.windowTitle() == "New Tax Code"

    def test_dialog_title_edit(self, qapp) -> None:
        from saebooks_desktop.views.tax_codes import TaxCodeDialog

        dlg = TaxCodeDialog(existing=_SAMPLE_CODES[0])
        assert dlg.windowTitle() == "Edit Tax Code"

    def test_dialog_pre_populated_for_edit(self, qapp) -> None:
        from saebooks_desktop.views.tax_codes import TaxCodeDialog

        dlg = TaxCodeDialog(existing=_SAMPLE_CODES[0])
        assert dlg._code_edit.text() == "GST"
        assert dlg._name_edit.text() == "Goods and Services Tax"
        assert dlg._rate_edit.text() == "10.0"

    def test_current_data_returns_form_values(self, qapp) -> None:
        from saebooks_desktop.views.tax_codes import TaxCodeDialog

        dlg = TaxCodeDialog()
        dlg._code_edit.setText("WET")
        dlg._name_edit.setText("Wine Equalisation Tax")
        dlg._rate_edit.setText("29.0")
        data = dlg.current_data()
        assert data["code"] == "WET"
        assert data["name"] == "Wine Equalisation Tax"
        assert data["rate"] == 29.0

    def test_has_tax_type_combo(self, qapp) -> None:
        from PySide6.QtWidgets import QComboBox

        from saebooks_desktop.views.tax_codes import TaxCodeDialog

        dlg = TaxCodeDialog()
        assert isinstance(dlg._type_combo, QComboBox)

    def test_type_combo_contains_gst(self, qapp) -> None:
        from saebooks_desktop.views.tax_codes import TaxCodeDialog

        dlg = TaxCodeDialog()
        options = [dlg._type_combo.itemText(i) for i in range(dlg._type_combo.count())]
        assert "GST" in options
        assert "FRE" in options
