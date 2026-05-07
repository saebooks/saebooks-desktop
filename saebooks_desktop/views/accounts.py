"""Accounts (Chart of Accounts) view.

Displays the full CoA in a QTreeView backed by QStandardItemModel.
Accounts are loaded once (no pagination) — the AU seed has ~80-120 rows.

Columns: Code | Name | Type | Balance (right-aligned currency)

Filter toolbar (above tree):
  - QLineEdit search box — live filter by code or name
  - QComboBox account type (All / Asset / Liability / Equity / Income / Expense)
  - "New Account" QPushButton (emits ``new_account_requested``)

Signals:
  - ``account_selected(str)``  — emitted on double-click with the account id.
  - ``new_account_requested()`` — emitted when "New Account" is clicked.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.accounts import list_accounts
from saebooks_desktop.services.api_client import APIClient, ServerOfflineError

# Column indices
_COL_CODE = 0
_COL_NAME = 1
_COL_TYPE = 2
_COL_BALANCE = 3

_COLUMNS = ["Code", "Name", "Type", "Balance"]

_TYPE_OPTIONS = ["All", "Asset", "Liability", "Equity", "Income", "Expense"]


class AccountsView(QWidget):
    """Chart of Accounts list view.

    Fetches from ``/api/v1/accounts`` via REST and renders a filterable
    tree.  Emits ``account_selected(id)`` on double-click.
    """

    account_selected = Signal(str)
    new_account_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._client = APIClient()
        # Full unfiltered data, kept so live filtering doesn't re-fetch.
        self._all_accounts: list[dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # --- Filter toolbar ---
        toolbar_widget = QWidget()
        toolbar_layout = QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)

        toolbar_layout.addWidget(QLabel("Search:"))
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Code or name…")
        self._search_box.textChanged.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self._search_box)

        toolbar_layout.addWidget(QLabel("Type:"))
        self._type_combo = QComboBox()
        self._type_combo.addItems(_TYPE_OPTIONS)
        self._type_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self._type_combo)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        toolbar_layout.addWidget(spacer)

        self._new_btn = QPushButton("New Account")
        self._new_btn.clicked.connect(self.new_account_requested)
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

        # --- Tree ---
        self._model = QStandardItemModel(0, len(_COLUMNS))
        self._model.setHorizontalHeaderLabels(_COLUMNS)

        # Right-align the Balance column header
        self._model.horizontalHeaderItem(_COL_BALANCE).setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self._tree.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self._tree.header().setStretchLastSection(True)

        self._tree.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._tree)

        self._load_accounts()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Re-fetch from server and rebuild the tree."""
        self._load_accounts()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _active_type_filter(self) -> str | None:
        text = self._type_combo.currentText()
        return None if text == "All" else text.lower()

    def _active_search(self) -> str:
        return self._search_box.text().strip().lower()

    def _load_accounts(self) -> None:
        self._offline_label.setVisible(False)
        try:
            self._all_accounts = list_accounts(self._client)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._offline_label.setVisible(True)
            return

        self._rebuild_model()

    def _rebuild_model(self) -> None:
        """Repopulate the model applying the current search/type filters."""
        self._model.removeRows(0, self._model.rowCount())

        search = self._active_search()
        type_filter = self._active_type_filter()

        for acc in self._all_accounts:
            acc_type = (acc.get("type") or "").lower()
            acc_code = (acc.get("code") or "").lower()
            acc_name = (acc.get("name") or "").lower()

            if type_filter and acc_type != type_filter:
                continue
            if search and search not in acc_code and search not in acc_name:
                continue

            row = self._model.rowCount()
            self._model.insertRow(row)

            self._model.setItem(row, _COL_CODE, QStandardItem(acc.get("code") or ""))
            self._model.setItem(row, _COL_NAME, QStandardItem(acc.get("name") or ""))
            self._model.setItem(row, _COL_TYPE, QStandardItem(acc.get("type") or ""))

            balance_item = QStandardItem(acc.get("balance") or "")
            balance_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._model.setItem(row, _COL_BALANCE, balance_item)

            # Store the account id for double-click signal on the code column item
            self._model.item(row, _COL_CODE).setData(
                acc.get("id") or "", Qt.ItemDataRole.UserRole
            )

    def _on_filter_changed(self) -> None:
        self._rebuild_model()

    def _on_double_click(self, index: object) -> None:
        row = index.row()  # type: ignore[union-attr]
        id_item = self._model.item(row, _COL_CODE)
        if id_item is not None:
            account_id = id_item.data(Qt.ItemDataRole.UserRole)
            if account_id:
                self.account_selected.emit(str(account_id))

    def _on_export_clicked(self) -> None:
        """Export the current model to CSV via a save dialog."""
        from PySide6.QtWidgets import QMessageBox

        from saebooks_desktop.services.csv_export import ensure_csv_path, export_model_to_csv

        path = ensure_csv_path(self, "accounts")
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
