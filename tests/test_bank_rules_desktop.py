"""Tests for BankRulesView and CreateBankRuleDialog.

All tests run without a real API server.  Service functions are patched at
their import points inside the view so no HTTP calls are made.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_PATCH_LIST = "saebooks_desktop.views.bank_rules.list_bank_rules"
_PATCH_CREATE = "saebooks_desktop.views.bank_rules.create_bank_rule"
_PATCH_ACCOUNTS = "saebooks_desktop.views.bank_rules.list_accounts"


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


_SAMPLE_RULES = [
    {
        "id": "br-001",
        "name": "Payroll Auto",
        "match_description": "PAYROLL",
        "account_name": "Wages Expense",
        "auto_apply": True,
    },
    {
        "id": "br-002",
        "name": "Rent",
        "match_description": "RENT",
        "account_name": "Rent Expense",
        "auto_apply": False,
    },
    {
        "id": "br-003",
        "name": "Telco",
        "match_description": "TELSTRA",
        "account_name": "Telephone Expense",
        "auto_apply": True,
    },
]


def _make_view(qapp, items=None, side_effect=None):
    from saebooks_desktop.views.bank_rules import BankRulesView

    if side_effect is not None:
        with patch(_PATCH_LIST, side_effect=side_effect):
            return BankRulesView()
    else:
        with patch(_PATCH_LIST, return_value=items if items is not None else []):
            return BankRulesView()


class TestBankRulesViewInstantiation:
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
        expected = ["Name", "Match Description", "Account", "Auto Apply"]
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
        assert view._new_btn.text() == "New Bank Rule"


class TestBankRulesViewModelPopulation:
    def test_row_count_matches_items(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_RULES)
        assert view._model.rowCount() == 3

    def test_name_column(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_RULES)
        assert view._model.item(0, 0).text() == "Payroll Auto"

    def test_match_description_column(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_RULES)
        assert view._model.item(0, 1).text() == "PAYROLL"
        assert view._model.item(1, 1).text() == "RENT"

    def test_account_column(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_RULES)
        assert view._model.item(0, 2).text() == "Wages Expense"

    def test_auto_apply_yes(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_RULES)
        assert view._model.item(0, 3).text() == "Yes"

    def test_auto_apply_no(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_RULES)
        assert view._model.item(1, 3).text() == "No"

    def test_id_stored_as_user_role(self, qapp) -> None:
        from PySide6.QtCore import Qt

        view = _make_view(qapp, items=_SAMPLE_RULES)
        stored_id = view._model.item(0, 0).data(Qt.ItemDataRole.UserRole)
        assert stored_id == "br-001"

    def test_empty_state_zero_rows(self, qapp) -> None:
        view = _make_view(qapp, items=[])
        assert view._model.rowCount() == 0


class TestBankRulesViewOffline:
    def test_offline_banner_shown_on_error(self, qapp) -> None:
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _make_view(qapp, side_effect=ServerOfflineError("offline"))
        assert not view._offline_label.isHidden()

    def test_offline_banner_hidden_when_data_loads(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_RULES)
        assert view._offline_label.isHidden()


class TestBankRulesViewDoubleClick:
    def test_double_click_emits_rule_selected(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_RULES)
        received: list[str] = []
        view.rule_selected.connect(received.append)
        index = view._model.index(0, 0)
        view._on_double_click(index)
        assert received == ["br-001"]

    def test_double_click_second_row(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_RULES)
        received: list[str] = []
        view.rule_selected.connect(received.append)
        index = view._model.index(2, 0)
        view._on_double_click(index)
        assert received == ["br-003"]


class TestBankRulesReload:
    def test_reload_replaces_rows(self, qapp) -> None:
        view = _make_view(qapp, items=_SAMPLE_RULES)
        assert view._model.rowCount() == 3
        with patch(_PATCH_LIST, return_value=[_SAMPLE_RULES[0]]):
            view.reload()
        assert view._model.rowCount() == 1


class TestCreateBankRuleDialog:
    def test_dialog_instantiates(self, qapp) -> None:
        from saebooks_desktop.views.bank_rules import CreateBankRuleDialog

        mock_client = MagicMock()
        with patch(_PATCH_ACCOUNTS, return_value=[]):
            dlg = CreateBankRuleDialog(mock_client)
        assert dlg is not None

    def test_dialog_has_account_combo(self, qapp) -> None:
        from PySide6.QtWidgets import QComboBox

        from saebooks_desktop.views.bank_rules import CreateBankRuleDialog

        mock_client = MagicMock()
        with patch(_PATCH_ACCOUNTS, return_value=[]):
            dlg = CreateBankRuleDialog(mock_client)
        assert isinstance(dlg._account_combo, QComboBox)

    def test_dialog_has_auto_apply_checkbox(self, qapp) -> None:
        from PySide6.QtWidgets import QCheckBox

        from saebooks_desktop.views.bank_rules import CreateBankRuleDialog

        mock_client = MagicMock()
        with patch(_PATCH_ACCOUNTS, return_value=[]):
            dlg = CreateBankRuleDialog(mock_client)
        assert isinstance(dlg._auto_check, QCheckBox)

    def test_current_data_returns_form_values(self, qapp) -> None:
        from saebooks_desktop.views.bank_rules import CreateBankRuleDialog

        mock_client = MagicMock()
        with patch(_PATCH_ACCOUNTS, return_value=[]):
            dlg = CreateBankRuleDialog(mock_client)
        dlg._name_edit.setText("Test Rule")
        dlg._match_edit.setText("AMAZON")
        dlg._auto_check.setChecked(True)
        data = dlg.current_data()
        assert data["name"] == "Test Rule"
        assert data["match_description"] == "AMAZON"
        assert data["auto_apply"] is True

    def test_accounts_populated_in_combo(self, qapp) -> None:
        from saebooks_desktop.views.bank_rules import CreateBankRuleDialog

        sample_accounts = [
            {"id": "acct-1", "code": "6100", "name": "Wages Expense"},
        ]
        mock_client = MagicMock()
        with patch(_PATCH_ACCOUNTS, return_value=sample_accounts):
            dlg = CreateBankRuleDialog(mock_client)
        # Should have "(none)" + 1 account
        assert dlg._account_combo.count() == 2
