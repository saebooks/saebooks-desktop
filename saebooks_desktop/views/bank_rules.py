"""Bank Rules list view.

Displays a QTableView of bank rules fetched from ``GET /api/v1/bank_rules``.

Columns: Name | Match Description | Account | Auto Apply

Toolbar:
  - "New Bank Rule" QPushButton  (opens create dialog)

Signals:
  - ``rule_selected(str)``      — emitted on double-click with the rule id.
  - ``new_rule_requested()``    — emitted after a new rule is created.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.accounts import list_accounts
from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.bank_rules import create_bank_rule, list_bank_rules

# Column indices
_COL_NAME = 0
_COL_MATCH = 1
_COL_ACCOUNT = 2
_COL_AUTO = 3

_COLUMNS = ["Name", "Match Description", "Account", "Auto Apply"]


class CreateBankRuleDialog(QDialog):
    """Modal dialog for creating a new bank rule."""

    def __init__(self, client: APIClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Bank Rule")
        self.setMinimumWidth(400)

        self._accounts: list[dict[str, Any]] = []

        form = QFormLayout()
        form.setContentsMargins(12, 12, 12, 12)

        self._name_edit = QLineEdit()
        self._match_edit = QLineEdit()
        self._account_combo = QComboBox()
        self._auto_check = QCheckBox("Auto apply")

        form.addRow("Name:", self._name_edit)
        form.addRow("Match Description:", self._match_edit)
        form.addRow("Account:", self._account_combo)
        form.addRow("", self._auto_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._populate_accounts(client)

    def _populate_accounts(self, client: APIClient) -> None:
        try:
            accounts = list_accounts(client)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            accounts = []
        self._accounts = accounts
        self._account_combo.addItem("(none)", "")
        for acct in accounts:
            label = f"{acct.get('code', '')} — {acct.get('name', '')}".strip(" —")
            self._account_combo.addItem(label, acct.get("id") or "")

    def _on_accept(self) -> None:
        if not self._name_edit.text().strip():
            QMessageBox.warning(self, "Validation", "Name is required.")
            return
        self.accept()

    def current_data(self) -> dict[str, Any]:
        return {
            "name": self._name_edit.text().strip(),
            "match_description": self._match_edit.text().strip(),
            "account_id": self._account_combo.currentData() or None,
            "auto_apply": self._auto_check.isChecked(),
        }


class BankRulesView(QWidget):
    """Bank Rules list view.

    Fetches from ``/api/v1/bank_rules`` via REST and renders a table.
    Emits ``rule_selected(id)`` on double-click.
    """

    rule_selected = Signal(str)
    new_rule_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._client = APIClient()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # --- Toolbar ---
        toolbar_widget = QWidget()
        toolbar_layout = QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        toolbar_layout.addWidget(spacer)

        self._new_btn = QPushButton("New Bank Rule")
        self._new_btn.clicked.connect(self._on_new_clicked)
        toolbar_layout.addWidget(self._new_btn)

        layout.addWidget(toolbar_widget)

        # --- Offline banner ---
        self._offline_label = QLabel("Server offline — showing cached data")
        self._offline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._offline_label.setStyleSheet(
            "background: #fff3cd; color: #856404; padding: 4px;"
        )
        self._offline_label.setVisible(False)
        layout.addWidget(self._offline_label)

        # --- Table ---
        self._model = QStandardItemModel(0, len(_COLUMNS))
        self._model.setHorizontalHeaderLabels(_COLUMNS)

        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setStretchLastSection(True)

        self._table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        self._load_rules()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Re-fetch all bank rules."""
        self._load_rules()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_rules(self) -> None:
        self._model.removeRows(0, self._model.rowCount())
        self._offline_label.setVisible(False)
        try:
            items = list_bank_rules(self._client)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._offline_label.setVisible(True)
            return
        self._append_rows(items)

    def _append_rows(self, rules: list[dict[str, Any]]) -> None:
        for rule in rules:
            row = self._model.rowCount()
            self._model.insertRow(row)

            name_item = QStandardItem(rule.get("name") or "")
            name_item.setData(rule.get("id") or "", Qt.ItemDataRole.UserRole)
            self._model.setItem(row, _COL_NAME, name_item)
            self._model.setItem(row, _COL_MATCH, QStandardItem(rule.get("match_description") or ""))
            self._model.setItem(row, _COL_ACCOUNT, QStandardItem(rule.get("account_name") or ""))
            auto_text = "Yes" if rule.get("auto_apply") else "No"
            self._model.setItem(row, _COL_AUTO, QStandardItem(auto_text))

    def _on_double_click(self, index: object) -> None:
        row = index.row()  # type: ignore[union-attr]
        id_item = self._model.item(row, _COL_NAME)
        if id_item is not None:
            rule_id = id_item.data(Qt.ItemDataRole.UserRole)
            if rule_id:
                self.rule_selected.emit(str(rule_id))

    def _on_new_clicked(self) -> None:
        dlg = CreateBankRuleDialog(self._client, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.current_data()
        try:
            create_bank_rule(self._client, data)
        except ServerOfflineError:
            QMessageBox.critical(self, "Offline", "Cannot create — server is offline.")
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"Create failed:\n{exc}")
            return
        self._load_rules()
        self.new_rule_requested.emit()
