"""Banking view — bank statement lines awaiting reconciliation.

Displays a paginated QTableView of bank statement lines (BSLs) fetched from
``GET /api/v1/bank-statement-lines``.

Columns: Date | Description | Reference | Debit | Credit | Balance | Status

Debit, Credit, and Balance are right-aligned currency columns.

The Status column is rendered with coloured text by ``_BslStatusDelegate``:
  - Unmatched → grey   (#888888)
  - Matched   → green  (#2e7d32)
  - Ignored   → orange (#e65100)

Filter toolbar (above table):
  - Account QComboBox   (populated from accounts with reconcile=True flag)
  - Status QComboBox    (All / Unmatched / Matched)
  - Date range pair     (QDateEdit "From" … "To")
  - "Import Statement" QPushButton  (emits ``import_requested``)
  - "Reconcile" QPushButton         (emits ``reconcile_requested`` with account_id)

Signals:
  - ``bsl_selected(str)``          — emitted on double-click with the BSL id.
  - ``import_requested()``         — emitted when "Import Statement" is clicked.
  - ``reconcile_requested(str)``   — emitted when "Reconcile" is clicked,
                                     carries the currently selected account_id.

Pagination: "Load more" button appends the next page; ``_current_page``
tracks the current position.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.accounts import list_accounts
from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.banking import list_bank_statement_lines

# Column indices
_COL_DATE = 0
_COL_DESCRIPTION = 1
_COL_REFERENCE = 2
_COL_DEBIT = 3
_COL_CREDIT = 4
_COL_BALANCE = 5
_COL_STATUS = 6

_COLUMNS = ["Date", "Description", "Reference", "Debit", "Credit", "Balance", "Status"]

# Status colours (foreground)
_STATUS_COLORS: dict[str, QColor] = {
    "unmatched": QColor("#888888"),
    "matched": QColor("#2e7d32"),
    "ignored": QColor("#e65100"),
}

_STATUS_OPTIONS = ["All", "Unmatched", "Matched"]

_PAGE_SIZE = 50

# Sentinel stored in the account combo's UserRole when "All accounts" is selected.
_ALL_ACCOUNTS_ID = ""


class _BslStatusDelegate(QStyledItemDelegate):
    """Render the Status column with a coloured foreground."""

    def initStyleOption(
        self, option: QStyleOptionViewItem, index: object
    ) -> None:
        super().initStyleOption(option, index)  # type: ignore[arg-type]
        raw = index.data(Qt.ItemDataRole.DisplayRole) or ""  # type: ignore[union-attr]
        colour = _STATUS_COLORS.get(raw.lower())
        if colour:
            option.palette.setColor(option.palette.ColorRole.Text, colour)  # type: ignore[union-attr]


class BankingView(QWidget):
    """Banking view — bank statement lines list.

    Fetches from ``/api/v1/bank-statement-lines`` via REST and renders a
    filterable, paginated table.  Emits ``bsl_selected(id)`` on double-click.
    """

    bsl_selected = Signal(str)
    import_requested = Signal()
    reconcile_requested = Signal(str)

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

        toolbar_layout.addWidget(QLabel("Account:"))
        self._account_combo = QComboBox()
        self._account_combo.addItem("All accounts", _ALL_ACCOUNTS_ID)
        self._account_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self._account_combo)

        toolbar_layout.addWidget(QLabel("Status:"))
        self._status_combo = QComboBox()
        self._status_combo.addItems(_STATUS_OPTIONS)
        self._status_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self._status_combo)

        toolbar_layout.addWidget(QLabel("From:"))
        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setSpecialValueText("Any")
        self._date_from.setMinimumDate(self._date_from.minimumDate())
        self._date_from.setDate(self._date_from.minimumDate())
        self._date_from.dateChanged.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self._date_from)

        toolbar_layout.addWidget(QLabel("To:"))
        self._date_to = QDateEdit()
        self._date_to.setCalendarPopup(True)
        self._date_to.setSpecialValueText("Any")
        self._date_to.setMinimumDate(self._date_to.minimumDate())
        self._date_to.setDate(self._date_to.minimumDate())
        self._date_to.dateChanged.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self._date_to)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        toolbar_layout.addWidget(spacer)

        self._import_btn = QPushButton("Import Statement")
        self._import_btn.clicked.connect(self.import_requested)
        toolbar_layout.addWidget(self._import_btn)

        self._reconcile_btn = QPushButton("Reconcile")
        self._reconcile_btn.clicked.connect(self._on_reconcile_clicked)
        toolbar_layout.addWidget(self._reconcile_btn)

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

        # Right-align currency column headers
        for col in (_COL_DEBIT, _COL_CREDIT, _COL_BALANCE):
            self._model.horizontalHeaderItem(col).setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setStretchLastSection(True)

        # Coloured status delegate
        self._table.setItemDelegateForColumn(_COL_STATUS, _BslStatusDelegate(self._table))

        self._table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        # --- Load more button ---
        self._load_more_btn = QPushButton("Load more")
        self._load_more_btn.clicked.connect(self._on_load_more)
        layout.addWidget(self._load_more_btn)

        # Populate bank account combo then load lines
        self._populate_accounts()
        self._load_lines(reset=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Re-fetch from page 1, respecting current filter state."""
        self._load_lines(reset=True)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _populate_accounts(self) -> None:
        """Load reconcilable accounts into the account combo."""
        try:
            accounts = list_accounts(self._client)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            return

        # Block signals while populating to avoid triggering repeated reloads
        self._account_combo.blockSignals(True)
        for acct in accounts:
            if acct.get("reconcile") or acct.get("is_bank_account"):
                label = f"{acct.get('code', '')} — {acct.get('name', '')}".strip(" —")
                self._account_combo.addItem(label, acct.get("id") or "")
        self._account_combo.blockSignals(False)

    def _active_account_id(self) -> str | None:
        acct_id = self._account_combo.currentData()
        return None if acct_id == _ALL_ACCOUNTS_ID else acct_id

    def _active_status_filter(self) -> str | None:
        text = self._status_combo.currentText()
        return None if text == "All" else text.lower()

    def _active_date_from(self) -> str | None:
        d = self._date_from.date()
        if d == self._date_from.minimumDate():
            return None
        return d.toString("yyyy-MM-dd")

    def _active_date_to(self) -> str | None:
        d = self._date_to.date()
        if d == self._date_to.minimumDate():
            return None
        return d.toString("yyyy-MM-dd")

    def _load_lines(self, reset: bool = False) -> None:
        if reset:
            self._current_page = 1
            self._model.removeRows(0, self._model.rowCount())
            self._has_more = True

        self._offline_label.setVisible(False)
        try:
            items = list_bank_statement_lines(
                self._client,
                account_id=self._active_account_id(),
                page=self._current_page,
                page_size=_PAGE_SIZE,
                status_filter=self._active_status_filter(),
                date_from=self._active_date_from(),
                date_to=self._active_date_to(),
            )
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._offline_label.setVisible(True)
            return

        self._append_rows(items)

        if len(items) < _PAGE_SIZE:
            self._has_more = False

        self._load_more_btn.setEnabled(self._has_more)

    def _append_rows(self, lines: list[dict[str, Any]]) -> None:
        for line in lines:
            row = self._model.rowCount()
            self._model.insertRow(row)

            self._model.setItem(row, _COL_DATE, QStandardItem(line.get("date") or ""))
            self._model.setItem(
                row, _COL_DESCRIPTION, QStandardItem(line.get("description") or "")
            )
            self._model.setItem(
                row, _COL_REFERENCE, QStandardItem(line.get("reference") or "")
            )

            for col, key in (
                (_COL_DEBIT, "debit"),
                (_COL_CREDIT, "credit"),
                (_COL_BALANCE, "balance"),
            ):
                amt_item = QStandardItem(line.get(key) or "")
                amt_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self._model.setItem(row, col, amt_item)

            self._model.setItem(
                row, _COL_STATUS, QStandardItem(line.get("status") or "")
            )

            # Store the BSL id for double-click signal on the date column item
            self._model.item(row, _COL_DATE).setData(
                line.get("id") or "", Qt.ItemDataRole.UserRole
            )

    def _on_filter_changed(self) -> None:
        self._load_lines(reset=True)

    def _on_load_more(self) -> None:
        if not self._has_more:
            return
        self._current_page += 1
        self._load_lines(reset=False)

    def _on_double_click(self, index: object) -> None:
        row = index.row()  # type: ignore[union-attr]
        id_item = self._model.item(row, _COL_DATE)
        if id_item is not None:
            bsl_id = id_item.data(Qt.ItemDataRole.UserRole)
            if bsl_id:
                self.bsl_selected.emit(str(bsl_id))

    def _on_reconcile_clicked(self) -> None:
        account_id = self._active_account_id() or ""
        self.reconcile_requested.emit(account_id)

    def _on_export_clicked(self) -> None:
        """Export the current model to CSV via a save dialog."""
        from PySide6.QtWidgets import QMessageBox

        from saebooks_desktop.services.csv_export import ensure_csv_path, export_model_to_csv

        path = ensure_csv_path(self, "bank-statement-lines")
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
