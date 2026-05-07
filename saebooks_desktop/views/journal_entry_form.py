"""Journal Entry create/edit form.

Used for both CREATE (new blank) and EDIT (pre-filled from an existing entry).

Constructor:
    JournalEntryForm(client, je_id=None, parent=None)

If ``je_id`` is provided the form loads the existing entry via
``GET /api/v1/journal_entries/{id}`` and pre-fills all fields.

Signals:
    journal_saved(str)  — emitted with the saved journal entry id after success
    cancelled()         — emitted when Cancel is clicked
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
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

from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.journal_entry_form import (
    create_journal_entry,
    list_all_accounts,
    post_journal_entry,
    update_journal_entry,
)

# Line-items table column indices
_COL_ACCOUNT = 0
_COL_DESC = 1
_COL_DEBIT = 2
_COL_CREDIT = 3
_COL_REMOVE = 4

_LINE_COLUMNS = ["Account", "Description", "Debit", "Credit", ""]

_MIN_LINES = 2


class JournalEntryForm(QWidget):
    """Create/edit form for a single journal entry.

    In create mode (``je_id=None``) the form starts blank with two lines.
    In edit mode an existing entry is loaded and fields pre-filled.

    The Debit and Credit spinboxes on each row are mutually exclusive — setting
    one non-zero clears the other.  The Save buttons are disabled when total
    debits do not equal total credits.
    """

    journal_saved = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        client: APIClient,
        je_id: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._client = client
        self._je_id = je_id
        self._etag: int | None = None
        self._accounts: list[dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # --- Error / offline banner ---
        self._banner = QLabel()
        self._banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._banner.setVisible(False)
        layout.addWidget(self._banner)

        # --- Header section ---
        header_frame = QFrame()
        header_frame.setFrameShape(QFrame.Shape.StyledPanel)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setSpacing(6)

        # Date / Reference / Narration row
        date_row = QWidget()
        date_layout = QHBoxLayout(date_row)
        date_layout.setContentsMargins(0, 0, 0, 0)
        today = QDate.currentDate()
        date_layout.addWidget(QLabel("Date:"))
        self._date_edit = QDateEdit(today)
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        date_layout.addWidget(self._date_edit)
        date_layout.addWidget(QLabel("Reference:"))
        self._reference_edit = QLineEdit()
        self._reference_edit.setPlaceholderText("Optional")
        date_layout.addWidget(self._reference_edit)
        header_layout.addWidget(date_row)

        narration_row = QWidget()
        narration_layout = QHBoxLayout(narration_row)
        narration_layout.setContentsMargins(0, 0, 0, 0)
        narration_layout.addWidget(QLabel("Narration:"))
        self._narration_edit = QLineEdit()
        self._narration_edit.setPlaceholderText("Description of this journal entry")
        narration_layout.addWidget(self._narration_edit)
        header_layout.addWidget(narration_row)

        layout.addWidget(header_frame)

        # --- Line items table ---
        self._lines_table = QTableWidget(0, len(_LINE_COLUMNS))
        self._lines_table.setHorizontalHeaderLabels(_LINE_COLUMNS)
        self._lines_table.horizontalHeader().setStretchLastSection(False)
        self._lines_table.horizontalHeader().setSectionResizeMode(
            _COL_DESC, self._lines_table.horizontalHeader().ResizeMode.Stretch
        )
        self._lines_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        layout.addWidget(self._lines_table, 1)

        # Add line button
        add_line_row = QWidget()
        add_line_layout = QHBoxLayout(add_line_row)
        add_line_layout.setContentsMargins(0, 0, 0, 0)
        self._add_line_btn = QPushButton("Add Line")
        self._add_line_btn.clicked.connect(self._on_add_line)
        add_line_layout.addWidget(self._add_line_btn)
        add_line_layout.addStretch()
        layout.addWidget(add_line_row)

        # --- Totals footer ---
        totals_frame = QFrame()
        totals_layout = QVBoxLayout(totals_frame)
        totals_layout.setSpacing(4)

        self._dr_total_label = _right_label("0.00")
        self._cr_total_label = _right_label("0.00")
        self._diff_label = _right_label("0.00")

        diff_font = QFont()
        diff_font.setBold(True)
        self._diff_label.setFont(diff_font)

        totals_layout.addWidget(_labeled_row("Total Debits:", self._dr_total_label))
        totals_layout.addWidget(_labeled_row("Total Credits:", self._cr_total_label))
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        totals_layout.addWidget(sep)
        totals_layout.addWidget(_labeled_row("Difference (Dr - Cr):", self._diff_label))
        layout.addWidget(totals_frame)

        # --- Action toolbar ---
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 4, 0, 0)
        toolbar_spacer = QWidget()
        toolbar_spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        toolbar_layout.addWidget(toolbar_spacer)

        self._save_draft_btn = QPushButton("Save as Draft")
        self._save_draft_btn.clicked.connect(self._on_save_draft)
        toolbar_layout.addWidget(self._save_draft_btn)

        self._save_post_btn = QPushButton("Save && Post")
        self._save_post_btn.clicked.connect(self._on_save_post)
        toolbar_layout.addWidget(self._save_post_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.cancelled)
        toolbar_layout.addWidget(self._cancel_btn)

        layout.addWidget(toolbar)

        # Load reference data
        self._load_reference_data()

        if self._je_id:
            self._load_existing_entry()
        else:
            # Start with two blank lines (min for a valid journal)
            self._append_blank_line()
            self._append_blank_line()

        self._recalculate_totals()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def line_count(self) -> int:
        """Return the current number of line rows."""
        return self._lines_table.rowCount()

    def is_balanced(self) -> bool:
        """Return True when total debits == total credits."""
        dr, cr = self._sum_dr_cr()
        return abs(dr - cr) < 0.005

    # ------------------------------------------------------------------
    # Reference data
    # ------------------------------------------------------------------

    def _load_reference_data(self) -> None:
        """Fetch all accounts from the API."""
        try:
            self._accounts = list_all_accounts(self._client)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._accounts = []

    # ------------------------------------------------------------------
    # Edit mode — load existing entry
    # ------------------------------------------------------------------

    def _load_existing_entry(self) -> None:
        """Fetch existing journal entry and pre-fill form fields."""
        assert self._je_id is not None
        try:
            data = self._client.get(f"/api/v1/journal_entries/{self._je_id}")
        except (ServerOfflineError, Exception) as exc:  # noqa: BLE001
            self._show_banner(f"Could not load journal entry: {exc}", error=True)
            self._append_blank_line()
            self._append_blank_line()
            return

        self._etag = data.get("version")

        if data.get("entry_date"):
            self._date_edit.setDate(
                QDate.fromString(str(data["entry_date"]), "yyyy-MM-dd")
            )
        self._reference_edit.setText(data.get("reference") or "")
        self._narration_edit.setText(data.get("narration") or "")

        lines = data.get("lines") or []
        if lines:
            for line in lines:
                self._append_line_from_data(line)
        else:
            self._append_blank_line()
            self._append_blank_line()

        self._recalculate_totals()

    # ------------------------------------------------------------------
    # Line table helpers
    # ------------------------------------------------------------------

    def _append_blank_line(self) -> None:
        """Append a new blank editable row to the lines table."""
        row = self._lines_table.rowCount()
        self._lines_table.insertRow(row)
        self._populate_line_row(row, {})

    def _append_line_from_data(self, line: dict[str, Any]) -> None:
        """Append a row pre-filled from an existing line dict."""
        row = self._lines_table.rowCount()
        self._lines_table.insertRow(row)
        self._populate_line_row(row, line)

    def _populate_line_row(self, row: int, line: dict[str, Any]) -> None:
        """Wire up all cell widgets for a given row."""
        # Account combo
        account_combo = QComboBox()
        account_combo.addItem("-- Account --", userData=None)
        for acc in self._accounts:
            account_combo.addItem(
                acc.get("name") or str(acc.get("id", "")), userData=acc.get("id")
            )
        acc_id = str(line.get("account_id") or "")
        acc_idx = account_combo.findData(acc_id)
        if acc_idx >= 0:
            account_combo.setCurrentIndex(acc_idx)
        self._lines_table.setCellWidget(row, _COL_ACCOUNT, account_combo)

        # Description
        desc_edit = QLineEdit(line.get("description") or "")
        self._lines_table.setCellWidget(row, _COL_DESC, desc_edit)

        # Debit spinbox
        debit_spin = QDoubleSpinBox()
        debit_spin.setDecimals(2)
        debit_spin.setMinimum(0.0)
        debit_spin.setMaximum(9_999_999.99)
        debit_spin.setValue(float(line.get("debit") or 0.0))
        self._lines_table.setCellWidget(row, _COL_DEBIT, debit_spin)

        # Credit spinbox
        credit_spin = QDoubleSpinBox()
        credit_spin.setDecimals(2)
        credit_spin.setMinimum(0.0)
        credit_spin.setMaximum(9_999_999.99)
        credit_spin.setValue(float(line.get("credit") or 0.0))
        self._lines_table.setCellWidget(row, _COL_CREDIT, credit_spin)

        # Mutual exclusion: Dr > 0 clears Cr; Cr > 0 clears Dr
        debit_spin.valueChanged.connect(
            lambda val, r=row: self._on_debit_changed(r, val)
        )
        credit_spin.valueChanged.connect(
            lambda val, r=row: self._on_credit_changed(r, val)
        )

        # Remove button
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(lambda _, r=row: self._on_remove_line(r))
        self._lines_table.setCellWidget(row, _COL_REMOVE, remove_btn)

    def _on_add_line(self) -> None:
        """Append a blank row."""
        self._append_blank_line()
        self._recalculate_totals()

    def _on_remove_line(self, row: int) -> None:
        """Remove a row, enforcing minimum _MIN_LINES lines."""
        if self._lines_table.rowCount() <= _MIN_LINES:
            return
        self._lines_table.removeRow(row)
        self._rewire_row_signals()
        self._recalculate_totals()

    def _rewire_row_signals(self) -> None:
        """Re-connect spinbox and button signals after row index shifts."""
        for r in range(self._lines_table.rowCount()):
            debit_w = self._lines_table.cellWidget(r, _COL_DEBIT)
            credit_w = self._lines_table.cellWidget(r, _COL_CREDIT)
            remove_btn = self._lines_table.cellWidget(r, _COL_REMOVE)

            if debit_w is not None:
                try:
                    debit_w.valueChanged.disconnect()
                except RuntimeError:
                    pass
                debit_w.valueChanged.connect(
                    lambda val, row=r: self._on_debit_changed(row, val)
                )

            if credit_w is not None:
                try:
                    credit_w.valueChanged.disconnect()
                except RuntimeError:
                    pass
                credit_w.valueChanged.connect(
                    lambda val, row=r: self._on_credit_changed(row, val)
                )

            if remove_btn is not None:
                try:
                    remove_btn.clicked.disconnect()
                except RuntimeError:
                    pass
                remove_btn.clicked.connect(lambda _, row=r: self._on_remove_line(row))

    def _on_debit_changed(self, row: int, value: float) -> None:
        """If Debit is set > 0, clear Credit on the same row."""
        if value > 0.0:
            credit_w = self._lines_table.cellWidget(row, _COL_CREDIT)
            if credit_w is not None:
                credit_w.blockSignals(True)
                credit_w.setValue(0.0)
                credit_w.blockSignals(False)
        self._recalculate_totals()

    def _on_credit_changed(self, row: int, value: float) -> None:
        """If Credit is set > 0, clear Debit on the same row."""
        if value > 0.0:
            debit_w = self._lines_table.cellWidget(row, _COL_DEBIT)
            if debit_w is not None:
                debit_w.blockSignals(True)
                debit_w.setValue(0.0)
                debit_w.blockSignals(False)
        self._recalculate_totals()

    # ------------------------------------------------------------------
    # Totals
    # ------------------------------------------------------------------

    def _sum_dr_cr(self) -> tuple[float, float]:
        """Return (total_debit, total_credit) summed across all rows."""
        total_dr = 0.0
        total_cr = 0.0
        for row in range(self._lines_table.rowCount()):
            debit_w = self._lines_table.cellWidget(row, _COL_DEBIT)
            credit_w = self._lines_table.cellWidget(row, _COL_CREDIT)
            if debit_w is not None:
                total_dr += debit_w.value()
            if credit_w is not None:
                total_cr += credit_w.value()
        return total_dr, total_cr

    def _recalculate_totals(self) -> None:
        """Recalculate Dr/Cr totals and update footer labels and button states."""
        total_dr, total_cr = self._sum_dr_cr()
        diff = total_dr - total_cr

        self._dr_total_label.setText(f"{total_dr:.2f}")
        self._cr_total_label.setText(f"{total_cr:.2f}")
        self._diff_label.setText(f"{diff:.2f}")

        if abs(diff) < 0.005:
            self._diff_label.setStyleSheet("color: inherit;")
            self._save_draft_btn.setEnabled(True)
            self._save_post_btn.setEnabled(True)
        else:
            self._diff_label.setStyleSheet("color: #c62828;")
            self._save_draft_btn.setEnabled(False)
            self._save_post_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Build payload
    # ------------------------------------------------------------------

    def _build_payload(self) -> dict[str, Any] | None:
        """Validate form and return API payload, or None if invalid."""
        if self._lines_table.rowCount() == 0:
            self._show_banner("At least two line items are required.", error=True)
            return None

        if not self.is_balanced():
            self._show_banner("Debits must equal credits before saving.", error=True)
            return None

        lines = []
        for row in range(self._lines_table.rowCount()):
            acc_w = self._lines_table.cellWidget(row, _COL_ACCOUNT)
            desc_w = self._lines_table.cellWidget(row, _COL_DESC)
            debit_w = self._lines_table.cellWidget(row, _COL_DEBIT)
            credit_w = self._lines_table.cellWidget(row, _COL_CREDIT)
            lines.append(
                {
                    "account_id": acc_w.currentData() if acc_w else None,
                    "description": desc_w.text() if desc_w else "",
                    "debit": str(debit_w.value()) if debit_w else "0",
                    "credit": str(credit_w.value()) if credit_w else "0",
                }
            )

        payload: dict[str, Any] = {
            "entry_date": self._date_edit.date().toString("yyyy-MM-dd"),
            "lines": lines,
        }
        narration = self._narration_edit.text().strip()
        if narration:
            payload["narration"] = narration
        reference = self._reference_edit.text().strip()
        if reference:
            payload["reference"] = reference

        return payload

    # ------------------------------------------------------------------
    # Save actions
    # ------------------------------------------------------------------

    def _on_save_draft(self) -> None:
        payload = self._build_payload()
        if payload is None:
            return
        self._do_save(payload, post_after=False)

    def _on_save_post(self) -> None:
        payload = self._build_payload()
        if payload is None:
            return
        self._do_save(payload, post_after=True)

    def _do_save(self, payload: dict[str, Any], *, post_after: bool) -> None:
        """Perform create or update then optionally post."""
        try:
            if self._je_id is None:
                # Create
                result = create_journal_entry(self._client, payload)
                saved_id = str(result.get("id", ""))
                saved_version = result.get("version")
            else:
                # Update
                etag = self._etag if self._etag is not None else 1
                status_code, result = update_journal_entry(
                    self._client, self._je_id, payload, etag
                )
                if status_code == 409:
                    self._show_banner(
                        "Version conflict — another user has modified this entry. "
                        "Please cancel and reload.",
                        error=True,
                    )
                    return
                saved_id = str(result.get("id", self._je_id))
                saved_version = result.get("version")

            if post_after:
                etag_for_post = saved_version if saved_version is not None else 1
                post_journal_entry(self._client, saved_id, etag_for_post)

        except Exception as exc:  # noqa: BLE001
            self._show_banner(f"Save failed: {exc}", error=True)
            return

        self.journal_saved.emit(saved_id)

    # ------------------------------------------------------------------
    # Banner helper
    # ------------------------------------------------------------------

    def _show_banner(self, message: str, *, error: bool = False) -> None:
        if error:
            style = "background: #fdecea; color: #c62828; padding: 4px;"
        else:
            style = "background: #e8f5e9; color: #2e7d32; padding: 4px;"
        self._banner.setStyleSheet(style)
        self._banner.setText(message)
        self._banner.setVisible(True)


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


def _right_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return lbl


def _labeled_row(label_text: str, value_widget: QLabel) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    spacer = QWidget()
    spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    layout.addWidget(spacer)
    layout.addWidget(QLabel(label_text))
    layout.addWidget(value_widget)
    return row
