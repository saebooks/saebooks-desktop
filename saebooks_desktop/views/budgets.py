"""Budgets list view.

Displays a paginated QTableView of budgets fetched from ``GET /api/v1/budgets``.

Columns: Name | Year | Status

Filter toolbar (above table):
  - Status QComboBox  (All / Active / Closed)
  - "New Budget" QPushButton

Signals:
  - ``budget_selected(str)``   — emitted on double-click with the budget id.
  - ``new_budget_requested()`` — emitted when "New Budget" is clicked.

Pagination: "Load more" button appends the next page.

Dialog:
  ``BudgetDialog`` — simple QDialog with Name + Fiscal Year fields.
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
from saebooks_desktop.services.budgets import create_budget, list_budgets

# Column indices
_COL_NAME = 0
_COL_YEAR = 1
_COL_STATUS = 2

_COLUMNS = ["Name", "Year", "Status"]

_STATUS_OPTIONS = ["All", "Active", "Closed"]

_PAGE_SIZE = 50


class BudgetsView(QWidget):
    """Budgets list view.

    Fetches from ``/api/v1/budgets`` via REST and renders a filterable,
    paginated table.  Emits ``budget_selected(id)`` on double-click.
    """

    budget_selected = Signal(str)
    new_budget_requested = Signal()

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

        self._new_btn = QPushButton("New Budget")
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

        # --- Load more button ---
        self._load_more_btn = QPushButton("Load more")
        self._load_more_btn.clicked.connect(self._on_load_more)
        layout.addWidget(self._load_more_btn)

        self._load_budgets(reset=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Re-fetch from page 1, respecting current filter state."""
        self._load_budgets(reset=True)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _active_status_filter(self) -> str | None:
        text = self._status_combo.currentText()
        return None if text == "All" else text.lower()

    def _load_budgets(self, reset: bool = False) -> None:
        if reset:
            self._current_page = 1
            self._model.removeRows(0, self._model.rowCount())
            self._has_more = True

        self._offline_label.setVisible(False)
        try:
            items = list_budgets(
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

    def _append_rows(self, budgets: list[dict[str, Any]]) -> None:
        for budget in budgets:
            row = self._model.rowCount()
            self._model.insertRow(row)

            name_item = QStandardItem(budget.get("name") or "")
            self._model.setItem(row, _COL_NAME, name_item)

            self._model.setItem(
                row, _COL_YEAR, QStandardItem(budget.get("fiscal_year") or "")
            )
            self._model.setItem(
                row, _COL_STATUS, QStandardItem(budget.get("status") or "")
            )

            # Store the budget id for double-click signal
            name_item.setData(budget.get("id") or "", Qt.ItemDataRole.UserRole)

    def _on_filter_changed(self) -> None:
        self._load_budgets(reset=True)

    def _on_load_more(self) -> None:
        if not self._has_more:
            return
        self._current_page += 1
        self._load_budgets(reset=False)

    def _on_double_click(self, index: object) -> None:
        row = index.row()  # type: ignore[union-attr]
        id_item = self._model.item(row, _COL_NAME)
        if id_item is not None:
            budget_id = id_item.data(Qt.ItemDataRole.UserRole)
            if budget_id:
                self.budget_selected.emit(str(budget_id))

    def _on_new_clicked(self) -> None:
        dlg = BudgetDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                create_budget(
                    self._client,
                    name=dlg.name(),
                    fiscal_year=dlg.fiscal_year(),
                )
            except (APIError, ServerOfflineError) as exc:
                QMessageBox.critical(self, "Create failed", str(exc))
                return
            self.reload()
            self.new_budget_requested.emit()


class BudgetDialog(QDialog):
    """Create-budget dialog — name and fiscal year fields.

    Desktop v1: line editing is deferred; this dialog covers creation only.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Budget")
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)

        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Operations 2024-25")
        form.addRow("Name:", self._name_edit)

        self._year_edit = QLineEdit()
        self._year_edit.setPlaceholderText("e.g. 2024-25")
        form.addRow("Fiscal Year:", self._year_edit)

        layout.addWidget(form_widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def name(self) -> str:
        """Return the entered budget name."""
        return self._name_edit.text().strip()

    def fiscal_year(self) -> str:
        """Return the entered fiscal year string."""
        return self._year_edit.text().strip()

    def _on_accept(self) -> None:
        if not self.name():
            QMessageBox.warning(self, "Validation", "Name is required.")
            return
        if not self.fiscal_year():
            QMessageBox.warning(self, "Validation", "Fiscal Year is required.")
            return
        self.accept()
