"""Projects list view.

Displays a paginated QTableView of projects fetched from ``GET /api/v1/projects``.

Columns: Code | Name | Contact | Budget | Spent | Status

Budget and Spent are right-aligned currency columns.

Filter toolbar (above table):
  - Status QComboBox  (All / Active / Closed)
  - "New Project" QPushButton

Signals:
  - ``project_selected(str)``   — emitted on double-click with the project id.
  - ``new_project_requested()`` — emitted when "New Project" is clicked.

Pagination: "Load more" button appends the next page.

Dialog:
  ``ProjectDialog`` — QDialog with Name, Code, Budget fields.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
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

from saebooks_desktop.services.api_client import APIClient, APIError, ServerOfflineError
from saebooks_desktop.services.projects import create_project, list_projects

# Column indices
_COL_CODE = 0
_COL_NAME = 1
_COL_CONTACT = 2
_COL_BUDGET = 3
_COL_SPENT = 4
_COL_STATUS = 5

_COLUMNS = ["Code", "Name", "Contact", "Budget", "Spent", "Status"]

_STATUS_OPTIONS = ["All", "Active", "Closed"]

_PAGE_SIZE = 50


class ProjectsView(QWidget):
    """Projects list view.

    Fetches from ``/api/v1/projects`` via REST and renders a filterable,
    paginated table.  Emits ``project_selected(id)`` on double-click.
    """

    project_selected = Signal(str)
    new_project_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._client = APIClient()
        self._current_page = 1
        self._has_more = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # --- Filter toolbar ---
        toolbar_widget = QWidget()
        toolbar_layout = QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)

        toolbar_layout.addWidget(QLabel("Status:"))
        self._status_combo = QComboBox()
        self._status_combo.addItems(_STATUS_OPTIONS)
        self._status_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self._status_combo)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        toolbar_layout.addWidget(spacer)

        self._new_btn = QPushButton("New Project")
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

        # Right-align Budget and Spent column headers
        for col in (_COL_BUDGET, _COL_SPENT):
            self._model.horizontalHeaderItem(col).setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setStretchLastSection(True)

        self._table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        # --- Load more button ---
        self._load_more_btn = QPushButton("Load more")
        self._load_more_btn.clicked.connect(self._on_load_more)
        layout.addWidget(self._load_more_btn)

        self._load_projects(reset=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Re-fetch from page 1, respecting current filter state."""
        self._load_projects(reset=True)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _active_status_filter(self) -> str | None:
        text = self._status_combo.currentText()
        return None if text == "All" else text.lower()

    def _load_projects(self, reset: bool = False) -> None:
        if reset:
            self._current_page = 1
            self._model.removeRows(0, self._model.rowCount())
            self._has_more = True

        self._offline_label.setVisible(False)
        try:
            items = list_projects(
                self._client,
                page=self._current_page,
                page_size=_PAGE_SIZE,
                status_filter=self._active_status_filter(),
            )
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._offline_label.setVisible(True)
            return

        self._append_rows(items)

        if len(items) < _PAGE_SIZE:
            self._has_more = False

        self._load_more_btn.setEnabled(self._has_more)

    def _append_rows(self, projects: list[dict[str, Any]]) -> None:
        for project in projects:
            row = self._model.rowCount()
            self._model.insertRow(row)

            code_item = QStandardItem(project.get("code") or "")
            self._model.setItem(row, _COL_CODE, code_item)

            self._model.setItem(
                row, _COL_NAME, QStandardItem(project.get("name") or "")
            )
            self._model.setItem(
                row,
                _COL_CONTACT,
                QStandardItem(
                    project.get("contact_name") or project.get("contact") or ""
                ),
            )

            budget_item = QStandardItem(str(project.get("budget") or ""))
            budget_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._model.setItem(row, _COL_BUDGET, budget_item)

            spent_item = QStandardItem(str(project.get("spent") or ""))
            spent_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._model.setItem(row, _COL_SPENT, spent_item)

            self._model.setItem(
                row, _COL_STATUS, QStandardItem(project.get("status") or "")
            )

            # Store the project id for double-click signal
            code_item.setData(project.get("id") or "", Qt.ItemDataRole.UserRole)

    def _on_filter_changed(self) -> None:
        self._load_projects(reset=True)

    def _on_load_more(self) -> None:
        if not self._has_more:
            return
        self._current_page += 1
        self._load_projects(reset=False)

    def _on_double_click(self, index: object) -> None:
        row = index.row()  # type: ignore[union-attr]
        id_item = self._model.item(row, _COL_CODE)
        if id_item is not None:
            project_id = id_item.data(Qt.ItemDataRole.UserRole)
            if project_id:
                self.project_selected.emit(str(project_id))

    def _on_new_clicked(self) -> None:
        dlg = ProjectDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                create_project(
                    self._client,
                    name=dlg.name(),
                    code=dlg.code(),
                    budget=dlg.budget(),
                )
            except (APIError, ServerOfflineError) as exc:
                QMessageBox.critical(self, "Create failed", str(exc))
                return
            self.reload()
            self.new_project_requested.emit()


class ProjectDialog(QDialog):
    """Create-project dialog — name, code, and budget fields."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)

        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Office Fit-out 2025")
        form.addRow("Name:", self._name_edit)

        self._code_edit = QLineEdit()
        self._code_edit.setPlaceholderText("e.g. PROJ-001")
        form.addRow("Code:", self._code_edit)

        self._budget_edit = QLineEdit()
        self._budget_edit.setPlaceholderText("e.g. 10000.00")
        form.addRow("Budget:", self._budget_edit)

        layout.addWidget(form_widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def name(self) -> str:
        """Return the entered project name."""
        return self._name_edit.text().strip()

    def code(self) -> str:
        """Return the entered project code."""
        return self._code_edit.text().strip()

    def budget(self) -> str:
        """Return the entered budget string."""
        return self._budget_edit.text().strip()

    def _on_accept(self) -> None:
        if not self.name():
            QMessageBox.warning(self, "Validation", "Name is required.")
            return
        if not self.code():
            QMessageBox.warning(self, "Validation", "Code is required.")
            return
        self.accept()
