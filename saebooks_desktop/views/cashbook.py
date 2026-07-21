"""Cashbook view — the engine's simplified single-bank-account bookkeeping mode.

Only shown for companies with ``bookkeeping_mode == "cashbook"`` (a full-mode
company 409s on every cashbook endpoint — see
``services.cashbook.is_cashbook_company``).

Layout:
  - Summary strip: three QLabels (Money in / Money out / Net) from
    ``GET /api/v1/cashbook/summary``.
  - Entries table (QTableWidget, read-only), newest first. Columns:
    Date | Direction | Category | Description | Amount.
  - "Add entry" button toggles an inline form (date, direction, category
    filtered by direction, description, amount) with Save/Cancel.
  - Delete button removes the selected row (soft-delete / reversing JE on
    the engine side) after a confirm dialog.

Degraded states:
  - ``ServerOfflineError`` → offline banner (objectName ``offline_banner``).
  - ``ModuleUnavailableError`` → module-unavailable banner (objectName
    ``module_banner``) carrying the engine's error message, and the Add
    button is disabled.

Signals:
  - ``entry_created(str)`` — emitted with the new entry's id after a
    successful Save.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.i18n import tr
from saebooks_desktop.services import period
from saebooks_desktop.services.api_client import (
    APIClient,
    APIError,
    ModuleUnavailableError,
    ServerOfflineError,
)
from saebooks_desktop.services.cashbook import (
    create_entry,
    delete_entry,
    get_summary,
    list_categories,
    list_entries,
)
from saebooks_desktop.services.company_settings import get_company
from saebooks_desktop.services.settings import get_company_id

#: Period-picker presets for the summary strip — same ids + labels as
#: saebooks-web's period picker, reusing the same i18n msgids via the
#: shared .mo catalogs (see i18n.py module docstring). Default index below
#: (calendar_ytd) matches services.cashbook.get_summary's own prior
#: default, so an unmodified load behaves identically to before this
#: picker existed.
_PERIOD_PRESET_OPTIONS: list[tuple[str, str]] = [
    ("this_fy", "This FY"),
    ("last_fy", "Last FY"),
    ("calendar_ytd", "Calendar year to date"),
    ("trailing_12", "Trailing 12 months"),
    ("this_quarter", "This quarter"),
]
_DEFAULT_PERIOD_PRESET_INDEX = 2  # "calendar_ytd"

_COL_DATE = 0
_COL_DIRECTION = 1
_COL_CATEGORY = 2
_COL_DESCRIPTION = 3
_COL_AMOUNT = 4

_COLUMNS = ["Date", "Direction", "Category", "Description", "Amount"]

_DIRECTION_LABELS = {"income": "In", "expense": "Out"}


def _extract_summary(s: dict[str, Any]) -> dict[str, str]:
    """Defensively pull income/expense/net out of a summary response.

    Tries the real engine field names (``income_total``/``expense_total``/
    ``net``) first, then a few plausible alternates so a schema drift
    doesn't blank the strip outright.
    """
    income = (
        s.get("income_total")
        or s.get("total_income")
        or s.get("money_in")
        or s.get("income")
        or "0"
    )
    expense = (
        s.get("expense_total")
        or s.get("total_expense")
        or s.get("money_out")
        or s.get("expense")
        or "0"
    )
    net = s.get("net") or s.get("net_total") or "0"
    return {"income": str(income), "expense": str(expense), "net": str(net)}


class CashbookView(QWidget):
    """Cashbook entries list + inline add form for single-bank-account companies."""

    entry_created = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._client = APIClient()
        self._categories: list[dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # --- Offline / module banners ---
        self._offline_banner = QLabel("Server offline — showing cached data")
        self._offline_banner.setObjectName("offline_banner")
        self._offline_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._offline_banner.setStyleSheet(
            "background: #fff3cd; color: #856404; padding: 4px;"
        )
        self._offline_banner.setVisible(False)
        layout.addWidget(self._offline_banner)

        self._module_banner = QLabel("")
        self._module_banner.setObjectName("module_banner")
        self._module_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._module_banner.setStyleSheet(
            "background: #f8d7da; color: #721c24; padding: 4px;"
        )
        self._module_banner.setVisible(False)
        layout.addWidget(self._module_banner)

        # --- Summary strip ---
        summary_widget = QWidget()
        summary_layout = QHBoxLayout(summary_widget)
        summary_layout.setContentsMargins(8, 4, 8, 4)

        self._money_in_label = QLabel("Money in: —")
        self._money_out_label = QLabel("Money out: —")
        self._net_label = QLabel("Net: —")
        for label in (self._money_in_label, self._money_out_label, self._net_label):
            summary_layout.addWidget(label)

        # --- Period picker (drives the summary strip's date range) ---
        self._period_combo = QComboBox()
        self._period_combo.setObjectName("period_combo")
        for preset_id, label in _PERIOD_PRESET_OPTIONS:
            self._period_combo.addItem(tr(label), preset_id)
        self._period_combo.setCurrentIndex(_DEFAULT_PERIOD_PRESET_INDEX)
        self._period_combo.currentIndexChanged.connect(self._on_period_changed)
        summary_layout.addWidget(self._period_combo)

        self._period_label = QLabel("")
        self._period_label.setObjectName("period_label")
        self._period_label.setStyleSheet("color: #666; font-size: 11px;")
        summary_layout.addWidget(self._period_label)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        summary_layout.addWidget(spacer)

        self._add_btn = QPushButton("Add entry")
        self._add_btn.clicked.connect(self._on_add_clicked)
        summary_layout.addWidget(self._add_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        summary_layout.addWidget(self._delete_btn)

        layout.addWidget(summary_widget)

        # --- Inline add-entry form (hidden until "Add entry" is clicked) ---
        self._form_widget = QWidget()
        form_layout = QHBoxLayout(self._form_widget)
        form_layout.setContentsMargins(8, 4, 8, 4)

        form_layout.addWidget(QLabel("Date:"))
        self._entry_date_edit = QDateEdit()
        self._entry_date_edit.setCalendarPopup(True)
        from PySide6.QtCore import QDate

        self._entry_date_edit.setDate(QDate.currentDate())
        form_layout.addWidget(self._entry_date_edit)

        form_layout.addWidget(QLabel("Direction:"))
        self._direction_combo = QComboBox()
        self._direction_combo.addItem("Income", "income")
        self._direction_combo.addItem("Expense", "expense")
        self._direction_combo.currentIndexChanged.connect(
            self._on_direction_changed
        )
        form_layout.addWidget(self._direction_combo)

        form_layout.addWidget(QLabel("Category:"))
        self._category_combo = QComboBox()
        form_layout.addWidget(self._category_combo)

        form_layout.addWidget(QLabel("Description:"))
        self._description_edit = QLineEdit()
        form_layout.addWidget(self._description_edit)

        form_layout.addWidget(QLabel("Amount:"))
        self._amount_edit = QLineEdit()
        self._amount_edit.setValidator(QDoubleValidator(0.01, 999999999.99, 2))
        form_layout.addWidget(self._amount_edit)

        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._on_save_clicked)
        form_layout.addWidget(self._save_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)
        form_layout.addWidget(self._cancel_btn)

        self._form_widget.setVisible(False)
        layout.addWidget(self._form_widget)

        self._form_error_label = QLabel("")
        self._form_error_label.setStyleSheet("color: #c62828;")
        self._form_error_label.setVisible(False)
        layout.addWidget(self._form_error_label)

        # --- Entries table ---
        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

    def showEvent(self, event) -> None:  # type: ignore[override]
        """First display triggers the initial load (keeps construction
        network-free for tests and window startup)."""
        super().showEvent(event)
        if not getattr(self, "_loaded_once", False):
            self._loaded_once = True
            self.load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, client: APIClient | None = None) -> None:
        """(Re)fetch categories, summary and entries; degrade gracefully.

        Never raises — offline/module-outage states are surfaced as
        banners instead.
        """
        if client is not None:
            self._client = client

        self._offline_banner.setVisible(False)
        self._module_banner.setVisible(False)
        self._add_btn.setEnabled(True)
        # Marks the view as loaded so _on_period_changed knows a later
        # combo change is a real user interaction, not construction-time
        # signal noise (mirrors DashboardView's same guard).
        self._loaded_once = True

        preset = self._period_combo.currentData() or "calendar_ytd"
        fin_year_start_month = self._fetch_fin_year_start_month(self._client)
        date_from, date_to, _active = period.resolve_period(
            preset, fin_year_start_month=fin_year_start_month
        )

        try:
            categories = list_categories(self._client)
            summary = get_summary(self._client, date_from=date_from, date_to=date_to)
            entries = list_entries(self._client, date_from=date_from, date_to=date_to)
        except ServerOfflineError:
            self._offline_banner.setVisible(True)
            return
        except ModuleUnavailableError as exc:
            self._module_banner.setText(str(exc))
            self._module_banner.setVisible(True)
            self._add_btn.setEnabled(False)
            return
        except (APIError, Exception):  # noqa: BLE001 — never raise out of load()
            return

        self._categories = categories
        self._populate_summary(summary)
        self._populate_category_combo()
        self._populate_entries(entries)
        self._period_label.setText(f"{date_from} → {date_to}")

    def _fetch_fin_year_start_month(self, client: APIClient) -> int:
        """Best-effort fetch of the active company's fin_year_start_month.

        Returns 7 (AU default) if no company is configured yet, the fetch
        fails, or the field is missing/unparseable.
        """
        company_id = get_company_id()
        if not company_id:
            return 7
        try:
            company = get_company(client, company_id)
            value = company.get("fin_year_start_month")
            return int(value) if value else 7
        except Exception:  # noqa: BLE001 — never block the cashbook load
            return 7

    def reload(self) -> None:
        """Alias for ``load()`` with the current client — matches sibling views."""
        self.load()

    def _on_period_changed(self, _index: int) -> None:
        if getattr(self, "_loaded_once", False):
            self.load()

    # ------------------------------------------------------------------
    # Private helpers — population
    # ------------------------------------------------------------------

    def _populate_summary(self, summary: dict[str, Any]) -> None:
        values = _extract_summary(summary)
        self._money_in_label.setText(f"Money in: {values['income']}")
        self._money_out_label.setText(f"Money out: {values['expense']}")
        self._net_label.setText(f"Net: {values['net']}")

    def _populate_category_combo(self) -> None:
        self._category_combo.blockSignals(True)
        self._category_combo.clear()
        direction = self._direction_combo.currentData() or "income"
        for cat in self._categories:
            if cat.get("direction") == direction:
                self._category_combo.addItem(
                    cat.get("label", cat.get("code", "")), cat.get("code")
                )
        self._category_combo.blockSignals(False)

    def _populate_entries(self, entries: list[dict[str, Any]]) -> None:
        self._table.setRowCount(0)
        ordered = sorted(
            entries, key=lambda e: e.get("entry_date") or "", reverse=True
        )
        for entry in ordered:
            row = self._table.rowCount()
            self._table.insertRow(row)

            date_item = QTableWidgetItem(entry.get("entry_date") or "")
            date_item.setData(Qt.ItemDataRole.UserRole, entry.get("id") or "")
            self._table.setItem(row, _COL_DATE, date_item)

            direction = entry.get("direction") or ""
            self._table.setItem(
                row,
                _COL_DIRECTION,
                QTableWidgetItem(_DIRECTION_LABELS.get(direction, direction)),
            )
            self._table.setItem(
                row,
                _COL_CATEGORY,
                QTableWidgetItem(
                    entry.get("category_label") or entry.get("category_code") or ""
                ),
            )
            self._table.setItem(
                row, _COL_DESCRIPTION, QTableWidgetItem(entry.get("description") or "")
            )
            amount_item = QTableWidgetItem(str(entry.get("amount") or ""))
            amount_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(row, _COL_AMOUNT, amount_item)

    # ------------------------------------------------------------------
    # Private helpers — form
    # ------------------------------------------------------------------

    def _clear_form(self) -> None:
        from PySide6.QtCore import QDate

        self._entry_date_edit.setDate(QDate.currentDate())
        self._direction_combo.setCurrentIndex(0)
        self._description_edit.clear()
        self._amount_edit.clear()
        self._form_error_label.setVisible(False)
        self._populate_category_combo()

    def _show_form_error(self, message: str) -> None:
        self._form_error_label.setText(message)
        self._form_error_label.setVisible(True)

    def _on_direction_changed(self) -> None:
        self._populate_category_combo()

    def _on_add_clicked(self) -> None:
        self._clear_form()
        self._form_widget.setVisible(True)

    def _on_cancel_clicked(self) -> None:
        self._form_widget.setVisible(False)
        self._form_error_label.setVisible(False)

    def _on_save_clicked(self) -> None:
        category_code = self._category_combo.currentData()
        if not category_code:
            self._show_form_error("Select a category.")
            return

        amount_text = self._amount_edit.text().strip()
        try:
            amount = float(amount_text)
        except ValueError:
            self._show_form_error("Enter a valid amount.")
            return
        if amount <= 0:
            self._show_form_error("Amount must be greater than zero.")
            return

        data: dict[str, Any] = {
            "entry_date": self._entry_date_edit.date().toString("yyyy-MM-dd"),
            "direction": self._direction_combo.currentData(),
            "category_code": category_code,
            "description": self._description_edit.text().strip() or None,
            "amount": amount_text,
        }

        try:
            result = create_entry(self._client, data)
        except ServerOfflineError:
            self._show_form_error("Cannot save — server is offline.")
            return
        except APIError as exc:
            self._show_form_error(f"Save failed: {exc}")
            return

        self._form_widget.setVisible(False)
        self._form_error_label.setVisible(False)
        self.load()
        self.entry_created.emit(str(result.get("id") or ""))

    # ------------------------------------------------------------------
    # Private helpers — delete
    # ------------------------------------------------------------------

    def _selected_entry_id(self) -> str | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, _COL_DATE)
        if item is None:
            return None
        entry_id = item.data(Qt.ItemDataRole.UserRole)
        return str(entry_id) if entry_id else None

    def _on_delete_clicked(self) -> None:
        entry_id = self._selected_entry_id()
        if not entry_id:
            return

        confirm = QMessageBox.question(
            self,
            "Delete entry",
            "Delete this cashbook entry? This posts a reversing entry.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_entry(self._client, entry_id)
        except ServerOfflineError:
            self._show_form_error("Cannot delete — server is offline.")
            return
        except APIError as exc:
            self._show_form_error(f"Delete failed: {exc}")
            return

        self.load()
