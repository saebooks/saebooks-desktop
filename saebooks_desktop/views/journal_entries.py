"""Journal Entries view.

Displays a paginated QTableView of posted journal entries from
``GET /api/v1/journal-entries``.

Columns: Date | Reference | Source | Narration | Dr Total | Cr Total

Dr Total and Cr Total are right-aligned currency.  For a valid double-entry
journal they are equal — this is a visual sanity check users expect.

Filter toolbar (above table):
  - Date range pair   (QDateEdit "From" … "To")
  - Source QComboBox  (All / Manual / Invoice / Bill / Payment / Reconciliation)
  - "New Journal" QPushButton  (emits ``new_journal_requested``)

Signals:
  - ``journal_selected(str)``  — emitted on double-click with the journal id.
  - ``new_journal_requested()`` — emitted when "New Journal" is clicked.

Pagination: "Load more" button appends the next page; ``_current_page``
tracks the current position.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.journal_entries import list_journal_entries

# Column indices
_COL_DATE = 0
_COL_REFERENCE = 1
_COL_SOURCE = 2
_COL_NARRATION = 3
_COL_DR_TOTAL = 4
_COL_CR_TOTAL = 5

_COLUMNS = ["Date", "Reference", "Source", "Narration", "Dr Total", "Cr Total"]

_SOURCE_OPTIONS = [
    "All",
    "Manual",
    "Invoice",
    "Bill",
    "Payment",
    "Reconciliation",
]

_PAGE_SIZE = 50


class JournalEntriesView(QWidget):
    """Journal Entries list view.

    Fetches from ``/api/v1/journal-entries`` via REST and renders a
    filterable, paginated table.  Emits ``journal_selected(id)`` on
    double-click.
    """

    journal_selected = Signal(str)
    new_journal_requested = Signal()

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

        toolbar_layout.addWidget(QLabel("Source:"))
        self._source_combo = QComboBox()
        self._source_combo.addItems(_SOURCE_OPTIONS)
        self._source_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self._source_combo)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        toolbar_layout.addWidget(spacer)

        self._new_btn = QPushButton("New Journal")
        self._new_btn.clicked.connect(self.new_journal_requested)
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

        # Right-align Dr Total and Cr Total header items
        self._model.horizontalHeaderItem(_COL_DR_TOTAL).setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._model.horizontalHeaderItem(_COL_CR_TOTAL).setTextAlignment(
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

        self._load_journals(reset=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Re-fetch from page 1, respecting current filter state."""
        self._load_journals(reset=True)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _active_source_filter(self) -> str | None:
        text = self._source_combo.currentText()
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

    def _load_journals(self, reset: bool = False) -> None:
        if reset:
            self._current_page = 1
            self._model.removeRows(0, self._model.rowCount())
            self._has_more = True

        self._offline_label.setVisible(False)
        try:
            items = list_journal_entries(
                self._client,
                page=self._current_page,
                page_size=_PAGE_SIZE,
                date_from=self._active_date_from(),
                date_to=self._active_date_to(),
                source_filter=self._active_source_filter(),
            )
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._offline_label.setVisible(True)
            return

        self._append_rows(items)

        if len(items) < _PAGE_SIZE:
            self._has_more = False

        self._load_more_btn.setEnabled(self._has_more)

    def _append_rows(self, entries: list[dict[str, Any]]) -> None:
        for entry in entries:
            row = self._model.rowCount()
            self._model.insertRow(row)

            self._model.setItem(row, _COL_DATE, QStandardItem(entry.get("date") or ""))
            self._model.setItem(
                row, _COL_REFERENCE, QStandardItem(entry.get("reference") or "")
            )
            self._model.setItem(
                row, _COL_SOURCE, QStandardItem(entry.get("source") or "")
            )
            self._model.setItem(
                row, _COL_NARRATION, QStandardItem(entry.get("narration") or "")
            )

            dr_item = QStandardItem(entry.get("dr_total") or "")
            dr_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._model.setItem(row, _COL_DR_TOTAL, dr_item)

            cr_item = QStandardItem(entry.get("cr_total") or "")
            cr_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._model.setItem(row, _COL_CR_TOTAL, cr_item)

            # Store the journal id for double-click signal on the date column item
            self._model.item(row, _COL_DATE).setData(
                entry.get("id") or "", Qt.ItemDataRole.UserRole
            )

    def _on_filter_changed(self) -> None:
        self._load_journals(reset=True)

    def _on_load_more(self) -> None:
        if not self._has_more:
            return
        self._current_page += 1
        self._load_journals(reset=False)

    def _on_double_click(self, index: object) -> None:
        row = index.row()  # type: ignore[union-attr]
        id_item = self._model.item(row, _COL_DATE)
        if id_item is not None:
            journal_id = id_item.data(Qt.ItemDataRole.UserRole)
            if journal_id:
                self.journal_selected.emit(str(journal_id))

    def _on_export_clicked(self) -> None:
        """Export the current model to CSV via a save dialog."""
        from PySide6.QtWidgets import QMessageBox

        from saebooks_desktop.services.csv_export import ensure_csv_path, export_model_to_csv

        path = ensure_csv_path(self, "journal-entries")
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
