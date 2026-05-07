"""Account Ranges list view.

Displays a QTableView of account ranges fetched from
``GET /api/v1/account_ranges``.

Columns: Name | Type | From Code | To Code

Toolbar:
  - "New Account Range" QPushButton  (opens create dialog)

Signals:
  - ``range_selected(str)``       — emitted on double-click with the range id.
  - ``new_range_requested()``     — emitted when "New Account Range" is clicked.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QComboBox,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.account_ranges import (
    create_account_range,
    list_account_ranges,
)

# Column indices
_COL_NAME = 0
_COL_TYPE = 1
_COL_FROM = 2
_COL_TO = 3

_COLUMNS = ["Name", "Type", "From Code", "To Code"]

_RANGE_TYPES = ["ASSET", "LIABILITY", "EQUITY", "INCOME", "EXPENSE", "OTHER"]


class CreateAccountRangeDialog(QDialog):
    """Modal dialog for creating a new account range."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Account Range")
        self.setMinimumWidth(360)

        form = QFormLayout()
        form.setContentsMargins(12, 12, 12, 12)

        self._name_edit = QLineEdit()
        self._type_combo = QComboBox()
        self._type_combo.addItems(_RANGE_TYPES)
        self._from_edit = QLineEdit()
        self._to_edit = QLineEdit()

        form.addRow("Name:", self._name_edit)
        form.addRow("Type:", self._type_combo)
        form.addRow("From Code:", self._from_edit)
        form.addRow("To Code:", self._to_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        if not self._name_edit.text().strip():
            QMessageBox.warning(self, "Validation", "Name is required.")
            return
        self.accept()

    def current_data(self) -> dict[str, Any]:
        return {
            "name": self._name_edit.text().strip(),
            "range_type": self._type_combo.currentText(),
            "from_code": self._from_edit.text().strip(),
            "to_code": self._to_edit.text().strip(),
        }


class AccountRangesView(QWidget):
    """Account Ranges list view.

    Fetches from ``/api/v1/account_ranges`` via REST and renders a table.
    Emits ``range_selected(id)`` on double-click.
    """

    range_selected = Signal(str)
    new_range_requested = Signal()

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

        self._new_btn = QPushButton("New Account Range")
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

        self._load_ranges()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Re-fetch all account ranges."""
        self._load_ranges()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_ranges(self) -> None:
        self._model.removeRows(0, self._model.rowCount())
        self._offline_label.setVisible(False)
        try:
            items = list_account_ranges(self._client)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._offline_label.setVisible(True)
            return
        self._append_rows(items)

    def _append_rows(self, ranges: list[dict[str, Any]]) -> None:
        for r in ranges:
            row = self._model.rowCount()
            self._model.insertRow(row)

            name_item = QStandardItem(r.get("name") or "")
            name_item.setData(r.get("id") or "", Qt.ItemDataRole.UserRole)
            self._model.setItem(row, _COL_NAME, name_item)
            self._model.setItem(row, _COL_TYPE, QStandardItem(r.get("range_type") or ""))
            self._model.setItem(row, _COL_FROM, QStandardItem(r.get("from_code") or ""))
            self._model.setItem(row, _COL_TO, QStandardItem(r.get("to_code") or ""))

    def _on_double_click(self, index: object) -> None:
        row = index.row()  # type: ignore[union-attr]
        id_item = self._model.item(row, _COL_NAME)
        if id_item is not None:
            range_id = id_item.data(Qt.ItemDataRole.UserRole)
            if range_id:
                self.range_selected.emit(str(range_id))

    def _on_new_clicked(self) -> None:
        dlg = CreateAccountRangeDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.current_data()
        try:
            create_account_range(self._client, data)
        except ServerOfflineError:
            QMessageBox.critical(self, "Offline", "Cannot create — server is offline.")
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"Create failed:\n{exc}")
            return
        self._load_ranges()
        self.new_range_requested.emit()
