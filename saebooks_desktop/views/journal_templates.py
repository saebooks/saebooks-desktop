"""Journal Templates list view.

Displays a QTableView of journal templates fetched from
``GET /api/v1/journal_templates``.

Columns: Name | Description | Line Count

Toolbar:
  - "New Template" QPushButton  (opens create dialog)

Signals:
  - ``template_selected(str)``   — emitted on double-click with the template id.
  - ``new_template_requested()`` — emitted after a new template is created.

Note: Line editing is not implemented in desktop v1 (too complex). The create
dialog only accepts name + description.
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
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.journal_templates import (
    create_journal_template,
    list_journal_templates,
)

# Column indices
_COL_NAME = 0
_COL_DESC = 1
_COL_LINES = 2

_COLUMNS = ["Name", "Description", "Line Count"]


class CreateJournalTemplateDialog(QDialog):
    """Modal dialog for creating a new journal template."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Journal Template")
        self.setMinimumWidth(380)

        form = QFormLayout()
        form.setContentsMargins(12, 12, 12, 12)

        self._name_edit = QLineEdit()
        self._desc_edit = QLineEdit()

        form.addRow("Name:", self._name_edit)
        form.addRow("Description:", self._desc_edit)

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
            "description": self._desc_edit.text().strip(),
        }


class JournalTemplatesView(QWidget):
    """Journal Templates list view.

    Fetches from ``/api/v1/journal_templates`` via REST and renders a table.
    Emits ``template_selected(id)`` on double-click.
    """

    template_selected = Signal(str)
    new_template_requested = Signal()

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

        self._new_btn = QPushButton("New Template")
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

        # Right-align Line Count header
        self._model.horizontalHeaderItem(_COL_LINES).setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setStretchLastSection(True)

        self._table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        self._load_templates()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Re-fetch all journal templates."""
        self._load_templates()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_templates(self) -> None:
        self._model.removeRows(0, self._model.rowCount())
        self._offline_label.setVisible(False)
        try:
            items = list_journal_templates(self._client)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._offline_label.setVisible(True)
            return
        self._append_rows(items)

    def _append_rows(self, templates: list[dict[str, Any]]) -> None:
        for tmpl in templates:
            row = self._model.rowCount()
            self._model.insertRow(row)

            name_item = QStandardItem(tmpl.get("name") or "")
            name_item.setData(tmpl.get("id") or "", Qt.ItemDataRole.UserRole)
            self._model.setItem(row, _COL_NAME, name_item)
            self._model.setItem(row, _COL_DESC, QStandardItem(tmpl.get("description") or ""))

            lines = tmpl.get("lines")
            if isinstance(lines, list):
                line_count = len(lines)
            else:
                line_count = tmpl.get("line_count") or 0
            line_item = QStandardItem(str(line_count))
            line_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._model.setItem(row, _COL_LINES, line_item)

    def _on_double_click(self, index: object) -> None:
        row = index.row()  # type: ignore[union-attr]
        id_item = self._model.item(row, _COL_NAME)
        if id_item is not None:
            tmpl_id = id_item.data(Qt.ItemDataRole.UserRole)
            if tmpl_id:
                self.template_selected.emit(str(tmpl_id))

    def _on_new_clicked(self) -> None:
        dlg = CreateJournalTemplateDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.current_data()
        try:
            create_journal_template(self._client, data)
        except ServerOfflineError:
            QMessageBox.critical(self, "Offline", "Cannot create — server is offline.")
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"Create failed:\n{exc}")
            return
        self._load_templates()
        self.new_template_requested.emit()
