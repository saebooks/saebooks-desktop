"""Reconciliation view — match unmatched bank statement lines to entries.

The reconcile loop for one account: list the unmatched bank statement
lines, pick a line, see suggested posted journal entries, and match with
one click; run auto-match across the whole account; unmatch a line you
matched by mistake. A running tally shows how many lines (and what value)
are still unmatched versus matched this session.

Design (mirrors BankingView + desktop UI-decisions §1 per-panel degrade):
  * Money is carried as strings and summed with Decimal — never float.
  * Every network call is isolated: ``ServerOfflineError`` shows the offline
    banner, other API errors show their message inline, and neither takes
    down the surrounding Banking stack.
  * Offscreen-testable: the service functions are imported at module scope
    so tests patch them; no HTTP happens under QT_QPA_PLATFORM=offscreen.

Signals:
  * ``back_requested()`` — user wants to return to the Banking list.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.reconciliation import (
    auto_match,
    list_unmatched,
    match,
    suggest_matches,
    unmatch,
)

_LINE_COLUMNS = ["Date", "Description", "Reference", "Amount"]
_COL_ID_ROLE = Qt.ItemDataRole.UserRole

_FILTER_UNMATCHED = "Unmatched"
_FILTER_MATCHED = "Matched this session"


def _to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, ValueError):
        return Decimal("0")


class ReconciliationView(QWidget):
    """Match unmatched bank statement lines to posted journal entries."""

    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client = APIClient()
        self._account_id: str = ""
        # BSLs matched during this session, keyed by id, so the user can
        # unmatch a mistaken match and the running totals stay honest
        # without a separate "all matched lines" endpoint.
        self._matched_session: dict[str, dict[str, Any]] = {}
        self._unmatched: list[dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # --- Header ---
        header = QHBoxLayout()
        self._back_btn = QPushButton("← Banking")
        self._back_btn.clicked.connect(self.back_requested)
        header.addWidget(self._back_btn)

        self._account_label = QLabel("Reconciliation")
        self._account_label.setStyleSheet("font-weight: 600;")
        header.addWidget(self._account_label)

        header.addStretch(1)

        header.addWidget(QLabel("Show:"))
        self._filter_combo = QComboBox()
        self._filter_combo.addItems([_FILTER_UNMATCHED, _FILTER_MATCHED])
        self._filter_combo.currentIndexChanged.connect(self._render_lines)
        header.addWidget(self._filter_combo)

        self._auto_btn = QPushButton("Auto-match all")
        self._auto_btn.clicked.connect(self._on_auto_match)
        header.addWidget(self._auto_btn)
        layout.addLayout(header)

        # --- Running totals ---
        self._totals_label = QLabel("")
        self._totals_label.setStyleSheet("color: #444; padding: 2px;")
        layout.addWidget(self._totals_label)

        # --- Banner (offline / errors / results) ---
        self._banner = QLabel("")
        self._banner.setWordWrap(True)
        self._banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._banner.setVisible(False)
        layout.addWidget(self._banner)

        # --- Body: lines table (left) + suggestions panel (right) ---
        body = QHBoxLayout()

        self._lines_model = QStandardItemModel(0, len(_LINE_COLUMNS))
        self._lines_model.setHorizontalHeaderLabels(_LINE_COLUMNS)
        self._lines_table = QTableView()
        self._lines_table.setModel(self._lines_model)
        self._lines_table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._lines_table.setSelectionBehavior(
            QTableView.SelectionBehavior.SelectRows
        )
        self._lines_table.horizontalHeader().setStretchLastSection(True)
        self._lines_table.clicked.connect(self._on_line_clicked)
        body.addWidget(self._lines_table, 2)

        # Right panel — swaps between suggestions and an unmatch action.
        self._detail_panel = QWidget()
        self._detail_layout = QVBoxLayout(self._detail_panel)
        self._detail_layout.setContentsMargins(8, 0, 0, 0)
        self._detail_hint = QLabel("Select a line to see suggested matches.")
        self._detail_hint.setWordWrap(True)
        self._detail_hint.setStyleSheet("color: #666;")
        self._detail_layout.addWidget(self._detail_hint)
        self._detail_layout.addStretch(1)
        body.addWidget(self._detail_panel, 1)

        layout.addLayout(body)

        self._update_totals()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_account(self, account_id: str, account_label: str | None = None) -> None:
        """Point the view at an account and refresh."""
        self._account_id = account_id or ""
        if account_label:
            self._account_label.setText(f"Reconcile — {account_label}")
        self._matched_session.clear()
        self._refresh()

    def reload(self) -> None:
        self._refresh()

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        self._clear_detail()
        if not self._account_id:
            self._unmatched = []
            self._render_lines()
            return
        try:
            self._unmatched = list_unmatched(self._client, self._account_id)
        except ServerOfflineError:
            self._unmatched = []
            self._show_banner("Server offline — cannot load lines.", ok=False)
        except Exception as exc:  # noqa: BLE001 — per-panel degrade
            self._unmatched = []
            self._show_banner(f"Could not load lines: {exc}", ok=False)
        else:
            self._hide_banner()
        self._render_lines()

    def _current_rows(self) -> list[dict[str, Any]]:
        if self._filter_combo.currentText() == _FILTER_MATCHED:
            return list(self._matched_session.values())
        return self._unmatched

    def _render_lines(self) -> None:
        self._lines_model.removeRows(0, self._lines_model.rowCount())
        for line in self._current_rows():
            row = self._lines_model.rowCount()
            self._lines_model.insertRow(row)
            self._lines_model.setItem(
                row, 0, QStandardItem(str(line.get("txn_date") or ""))
            )
            self._lines_model.setItem(
                row, 1, QStandardItem(str(line.get("description") or ""))
            )
            self._lines_model.setItem(
                row, 2, QStandardItem(str(line.get("reference") or ""))
            )
            amt = QStandardItem(str(line.get("amount") or ""))
            amt.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._lines_model.setItem(row, 3, amt)
            self._lines_model.item(row, 0).setData(
                line.get("id") or "", _COL_ID_ROLE
            )
        self._update_totals()

    def _update_totals(self) -> None:
        un_sum = sum((_to_decimal(l.get("amount")) for l in self._unmatched), Decimal("0"))
        mt = list(self._matched_session.values())
        mt_sum = sum((_to_decimal(l.get("amount")) for l in mt), Decimal("0"))
        self._totals_label.setText(
            f"Unmatched: {len(self._unmatched)} ({un_sum})  ·  "
            f"Matched this session: {len(mt)} ({mt_sum})"
        )

    # ------------------------------------------------------------------
    # Interactions
    # ------------------------------------------------------------------

    def _selected_line(self) -> dict[str, Any] | None:
        idxs = self._lines_table.selectionModel().selectedRows()
        if not idxs:
            return None
        row = idxs[0].row()
        id_item = self._lines_model.item(row, 0)
        if id_item is None:
            return None
        bsl_id = id_item.data(_COL_ID_ROLE)
        for line in self._current_rows():
            if line.get("id") == bsl_id:
                return line
        return None

    def _on_line_clicked(self, _index: object) -> None:
        line = self._selected_line()
        if line is None:
            return
        if self._filter_combo.currentText() == _FILTER_MATCHED:
            self._show_unmatch_action(line)
        else:
            self._show_suggestions(line)

    def _clear_detail(self) -> None:
        while self._detail_layout.count():
            item = self._detail_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

    def _show_suggestions(self, line: dict[str, Any]) -> None:
        self._clear_detail()
        header = QLabel(f"Suggestions for {line.get('amount')} — {line.get('description') or ''}")
        header.setWordWrap(True)
        header.setStyleSheet("font-weight: 600;")
        self._detail_layout.addWidget(header)

        try:
            suggestions = suggest_matches(self._client, line["id"])
        except ServerOfflineError:
            self._detail_layout.addWidget(QLabel("Server offline."))
            self._detail_layout.addStretch(1)
            return
        except Exception as exc:  # noqa: BLE001 — per-panel degrade
            self._detail_layout.addWidget(QLabel(f"Could not load suggestions: {exc}"))
            self._detail_layout.addStretch(1)
            return

        if not suggestions:
            self._detail_layout.addWidget(
                QLabel("No suggested matches. Post the record first, then reconcile.")
            )
            self._detail_layout.addStretch(1)
            return

        for sug in suggestions:
            row = QHBoxLayout()
            conf = sug.get("confidence")
            label = f"{sug.get('ref', '')} — {sug.get('description') or ''}"
            if conf:
                label += f"  [{conf}]"
            lbl = QLabel(label)
            lbl.setWordWrap(True)
            row.addWidget(lbl, 1)
            btn = QPushButton("Match")
            btn.clicked.connect(
                lambda _checked=False, bsl=line["id"], eid=sug["id"]: self._on_match(bsl, eid)
            )
            row.addWidget(btn)
            container = QWidget()
            container.setLayout(row)
            self._detail_layout.addWidget(container)
        self._detail_layout.addStretch(1)

    def _show_unmatch_action(self, line: dict[str, Any]) -> None:
        self._clear_detail()
        header = QLabel(f"Matched: {line.get('amount')} — {line.get('description') or ''}")
        header.setWordWrap(True)
        header.setStyleSheet("font-weight: 600;")
        self._detail_layout.addWidget(header)
        btn = QPushButton("Unmatch")
        btn.clicked.connect(lambda _checked=False, bsl=line["id"]: self._on_unmatch(bsl))
        self._detail_layout.addWidget(btn)
        self._detail_layout.addStretch(1)

    def _on_match(self, bsl_id: str, entry_id: str) -> None:
        line = next((l for l in self._unmatched if l.get("id") == bsl_id), None)
        try:
            match(self._client, bsl_id, entry_id)
        except ServerOfflineError:
            self._show_banner("Server offline — nothing was changed.", ok=False)
            return
        except Exception as exc:  # noqa: BLE001 — per-panel degrade
            self._show_banner(f"Match failed: {exc}", ok=False)
            return
        if line is not None:
            self._unmatched = [l for l in self._unmatched if l.get("id") != bsl_id]
            self._matched_session[bsl_id] = line
        self._show_banner("Line matched.", ok=True)
        self._clear_detail()
        self._render_lines()

    def _on_unmatch(self, bsl_id: str) -> None:
        line = self._matched_session.get(bsl_id)
        try:
            unmatch(self._client, bsl_id)
        except ServerOfflineError:
            self._show_banner("Server offline — nothing was changed.", ok=False)
            return
        except Exception as exc:  # noqa: BLE001 — per-panel degrade
            self._show_banner(f"Unmatch failed: {exc}", ok=False)
            return
        if line is not None:
            self._matched_session.pop(bsl_id, None)
            self._unmatched.append(line)
        self._show_banner("Line unmatched.", ok=True)
        self._clear_detail()
        self._render_lines()

    def _on_auto_match(self) -> None:
        if not self._account_id:
            return
        try:
            result = auto_match(self._client, self._account_id)
        except ServerOfflineError:
            self._show_banner("Server offline — nothing was changed.", ok=False)
            return
        except Exception as exc:  # noqa: BLE001 — per-panel degrade
            self._show_banner(f"Auto-match failed: {exc}", ok=False)
            return
        matched_n = result.get("matched", 0)
        self._show_banner(f"Auto-match complete — {matched_n} line(s) matched.", ok=True)
        # Auto-match links lines server-side; re-fetch to reflect the new state.
        self._refresh()

    # ------------------------------------------------------------------
    # Banner
    # ------------------------------------------------------------------

    def _show_banner(self, text: str, ok: bool) -> None:
        self._banner.setText(text)
        self._banner.setStyleSheet(
            "background: #e8f5e9; color: #2e7d32; padding: 4px;"
            if ok
            else "background: #fff3cd; color: #856404; padding: 4px;"
        )
        self._banner.setVisible(True)

    def _hide_banner(self) -> None:
        self._banner.setVisible(False)
