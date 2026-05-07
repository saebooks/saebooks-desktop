"""Contacts list view.

Displays a paginated QTableView of contacts fetched from ``GET /api/v1/contacts``.

Columns: Name | Type | Email | Phone | Balance

The Type column is rendered with coloured text by ``_TypeDelegate``:
  - Customer  → green  (#2e7d32)
  - Supplier  → blue   (#1565c0)
  - Employee  → grey   (#888888)
  - Other     → grey   (#888888)

Filter toolbar (above table):
  - Type QComboBox  (All / Customer / Supplier / Employee / Other)
  - QLineEdit search
  - "New Contact" QPushButton  (emits ``new_contact_requested``)
  - "Export CSV" QPushButton

Signals:
  - ``contact_selected(str)``   — emitted on double-click with the contact id.
  - ``new_contact_requested()`` — emitted when "New Contact" is clicked.

Pagination: "Load more" button appends the next page.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.contacts import list_contacts

# Column indices
_COL_NAME = 0
_COL_TYPE = 1
_COL_EMAIL = 2
_COL_PHONE = 3
_COL_BALANCE = 4

_COLUMNS = ["Name", "Type", "Email", "Phone", "Balance"]

# Type colours (foreground)
_TYPE_COLORS: dict[str, QColor] = {
    "customer": QColor("#2e7d32"),
    "supplier": QColor("#1565c0"),
    "employee": QColor("#888888"),
    "other": QColor("#888888"),
}

_TYPE_OPTIONS = ["All", "Customer", "Supplier", "Employee", "Other"]

_PAGE_SIZE = 50


class _TypeDelegate(QStyledItemDelegate):
    """Render the Type column with a coloured foreground."""

    def initStyleOption(
        self, option: QStyleOptionViewItem, index: object
    ) -> None:
        super().initStyleOption(option, index)  # type: ignore[arg-type]
        raw = index.data(Qt.ItemDataRole.DisplayRole) or ""  # type: ignore[union-attr]
        colour = _TYPE_COLORS.get(raw.lower())
        if colour:
            option.palette.setColor(option.palette.ColorRole.Text, colour)  # type: ignore[union-attr]


class ContactsView(QWidget):
    """Contacts list view.

    Fetches from ``/api/v1/contacts`` via REST and renders a filterable,
    paginated table.  Emits ``contact_selected(id)`` on double-click.
    """

    contact_selected = Signal(str)
    new_contact_requested = Signal()

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

        toolbar_layout.addWidget(QLabel("Type:"))
        self._type_combo = QComboBox()
        self._type_combo.addItems(_TYPE_OPTIONS)
        self._type_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self._type_combo)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search name or email…")
        self._search_edit.setMinimumWidth(200)
        self._search_edit.textChanged.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self._search_edit)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        toolbar_layout.addWidget(spacer)

        self._new_btn = QPushButton("New Contact")
        self._new_btn.clicked.connect(self.new_contact_requested)
        toolbar_layout.addWidget(self._new_btn)

        self._export_btn = QPushButton("Export CSV")
        self._export_btn.clicked.connect(self._on_export_clicked)
        toolbar_layout.addWidget(self._export_btn)

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

        # Right-align the Balance column header and cells
        self._model.horizontalHeaderItem(_COL_BALANCE).setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        # Coloured type delegate
        self._table.setItemDelegateForColumn(_COL_TYPE, _TypeDelegate(self._table))

        self._table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        # --- Load more button ---
        self._load_more_btn = QPushButton("Load more")
        self._load_more_btn.clicked.connect(self._on_load_more)
        layout.addWidget(self._load_more_btn)

        self._load_contacts(reset=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Re-fetch from page 1, respecting current filter state."""
        self._load_contacts(reset=True)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _active_type_filter(self) -> str | None:
        text = self._type_combo.currentText()
        return None if text == "All" else text.lower()

    def _active_search_query(self) -> str | None:
        text = self._search_edit.text().strip()
        return text if text else None

    def _load_contacts(self, reset: bool = False) -> None:
        if reset:
            self._current_page = 1
            self._model.removeRows(0, self._model.rowCount())
            self._has_more = True

        self._offline_label.setVisible(False)
        try:
            items = list_contacts(
                self._client,
                page=self._current_page,
                page_size=_PAGE_SIZE,
                type_filter=self._active_type_filter(),
                search_query=self._active_search_query(),
            )
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._offline_label.setVisible(True)
            return

        self._append_rows(items)

        if len(items) < _PAGE_SIZE:
            self._has_more = False

        self._load_more_btn.setEnabled(self._has_more)

    def _append_rows(self, contacts: list[dict[str, Any]]) -> None:
        for contact in contacts:
            row = self._model.rowCount()
            self._model.insertRow(row)

            name_item = QStandardItem(contact.get("name") or "")
            self._model.setItem(row, _COL_NAME, name_item)

            self._model.setItem(row, _COL_TYPE, QStandardItem(contact.get("type") or ""))
            self._model.setItem(row, _COL_EMAIL, QStandardItem(contact.get("email") or ""))
            self._model.setItem(row, _COL_PHONE, QStandardItem(contact.get("phone") or ""))

            balance_item = QStandardItem(contact.get("balance") or "")
            balance_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._model.setItem(row, _COL_BALANCE, balance_item)

            # Store the contact id for double-click signal
            name_item.setData(contact.get("id") or "", Qt.ItemDataRole.UserRole)

    def _on_filter_changed(self) -> None:
        self._load_contacts(reset=True)

    def _on_load_more(self) -> None:
        if not self._has_more:
            return
        self._current_page += 1
        self._load_contacts(reset=False)

    def _on_double_click(self, index: object) -> None:
        row = index.row()  # type: ignore[union-attr]
        id_item = self._model.item(row, _COL_NAME)
        if id_item is not None:
            contact_id = id_item.data(Qt.ItemDataRole.UserRole)
            if contact_id:
                self.contact_selected.emit(str(contact_id))

    def _on_export_clicked(self) -> None:
        """Export the current model to CSV via a save dialog."""
        from PySide6.QtWidgets import QMessageBox

        from saebooks_desktop.services.csv_export import ensure_csv_path, export_model_to_csv

        path = ensure_csv_path(self, "contacts")
        if path is None:
            return
        try:
            n = export_model_to_csv(self._model, path)
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", f"Could not write CSV:\n{exc}")
            return
        self._offline_label.setText(f"Exported {n} rows to {path.split('/')[-1]}")
        self._offline_label.setStyleSheet("background: #e8f5e9; color: #2e7d32; padding: 4px;")
        self._offline_label.setVisible(True)
