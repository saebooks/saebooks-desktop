"""Import Statement view — upload a bank statement (CSV/OFX) into an account.

Flow: pick a reconcilable chart account → choose a CSV/OFX file → preview
the first rows → Import. The engine auto-detects the CSV format and OFX, so
there is no column-mapping step. On success the imported lines become
UNMATCHED bank statement lines ready for the Reconciliation view.

Per-section error isolation (desktop UI-decisions §1 per-panel degrade):
a failure loading the account list, reading the file, or running the import
degrades to an inline banner on THIS view only — it never bubbles up to take
down the Banking stack. ``ServerOfflineError`` shows the offline banner;
other API errors show their message.

Signals:
  - ``import_done()``  — emitted after a successful commit (Banking reloads).
  - ``cancelled()``    — emitted when the user backs out.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.imports import run_bank_import
from saebooks_desktop.services.reconciliation import list_reconcilable_accounts

_PREVIEW_ROWS = 12


class ImportStatementView(QWidget):
    """Upload a bank statement file into a chosen reconcilable account."""

    import_done = Signal()
    cancelled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client = APIClient()
        self._raw: str = ""
        self._filename: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Import bank statement")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Upload a CSV or OFX file. Lines become unmatched statement "
            "lines you can reconcile."
        )
        subtitle.setStyleSheet("color: #666;")
        layout.addWidget(subtitle)

        # --- Account picker ---
        acct_row = QHBoxLayout()
        acct_row.addWidget(QLabel("Account:"))
        self._account_combo = QComboBox()
        acct_row.addWidget(self._account_combo, 1)
        layout.addLayout(acct_row)

        # --- File chooser ---
        file_row = QHBoxLayout()
        self._choose_btn = QPushButton("Choose file…")
        self._choose_btn.clicked.connect(self._on_choose_file)
        file_row.addWidget(self._choose_btn)
        self._file_label = QLabel("No file selected")
        self._file_label.setStyleSheet("color: #666;")
        file_row.addWidget(self._file_label, 1)
        layout.addLayout(file_row)

        # --- Preview ---
        self._preview = QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setPlaceholderText("A preview of the file appears here.")
        self._preview.setMaximumHeight(160)
        layout.addWidget(self._preview)

        # --- Status / error banner ---
        self._banner = QLabel("")
        self._banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._banner.setWordWrap(True)
        self._banner.setVisible(False)
        layout.addWidget(self._banner)

        # --- Action buttons ---
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.cancelled)
        btn_row.addWidget(self._cancel_btn)
        self._import_btn = QPushButton("Import")
        self._import_btn.setEnabled(False)
        self._import_btn.clicked.connect(self._on_import)
        btn_row.addWidget(self._import_btn)
        layout.addLayout(btn_row)

        layout.addStretch(1)

        self._populate_accounts()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Reset the form and re-fetch the account list (called on show)."""
        self._raw = ""
        self._filename = ""
        self._file_label.setText("No file selected")
        self._preview.setPlainText("")
        self._import_btn.setEnabled(False)
        self._hide_banner()
        self._populate_accounts()

    def select_account(self, account_id: str) -> None:
        """Pre-select an account by id (no-op if not present)."""
        idx = self._account_combo.findData(account_id)
        if idx >= 0:
            self._account_combo.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _populate_accounts(self) -> None:
        self._account_combo.clear()
        try:
            accounts = list_reconcilable_accounts(self._client)
        except ServerOfflineError:
            self._show_banner("Server offline — cannot load accounts.", ok=False)
            return
        except Exception as exc:  # noqa: BLE001 — per-panel degrade
            self._show_banner(f"Could not load accounts: {exc}", ok=False)
            return
        for acct in accounts:
            label = f"{acct.get('code', '')} — {acct.get('name', '')}".strip(" —")
            self._account_combo.addItem(label, acct.get("id") or "")

    def _current_account_id(self) -> str:
        return self._account_combo.currentData() or ""

    def _on_choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose a bank statement file",
            "",
            "Statement files (*.csv *.ofx *.txt);;All files (*)",
        )
        if not path:
            return
        self._load_file(path)

    def _load_file(self, path: str) -> None:
        """Read a file into the preview. Extracted for offscreen testing."""
        try:
            with open(path, "rb") as fh:
                self._raw = fh.read().decode("utf-8-sig", errors="replace")
        except OSError as exc:
            self._show_banner(f"Could not read file: {exc}", ok=False)
            self._import_btn.setEnabled(False)
            return
        self._filename = path.rsplit("/", 1)[-1]
        self._file_label.setText(self._filename)
        rows = [ln for ln in self._raw.splitlines() if ln.strip()][:_PREVIEW_ROWS]
        self._preview.setPlainText("\n".join(rows))
        self._hide_banner()
        self._import_btn.setEnabled(
            bool(self._raw.strip()) and bool(self._current_account_id())
        )

    def _on_import(self) -> None:
        account_id = self._current_account_id()
        if not account_id:
            self._show_banner("Choose an account first.", ok=False)
            return
        if not self._raw.strip():
            self._show_banner("Choose a file first.", ok=False)
            return
        self._import_btn.setEnabled(False)
        try:
            result: dict[str, Any] = run_bank_import(
                self._client, account_id, self._raw
            )
        except ServerOfflineError:
            self._show_banner("Server offline — nothing was imported.", ok=False)
            self._import_btn.setEnabled(True)
            return
        except Exception as exc:  # noqa: BLE001 — per-panel degrade
            self._show_banner(f"Import failed: {exc}", ok=False)
            self._import_btn.setEnabled(True)
            return

        inserted = result.get("inserted", 0)
        total = result.get("total", inserted)
        self._show_banner(
            f"Imported {inserted} of {total} lines"
            + (f" ({total - inserted} duplicate(s) skipped)." if total > inserted else "."),
            ok=True,
        )
        self.import_done.emit()

    def _show_banner(self, text: str, ok: bool) -> None:
        self._banner.setText(text)
        if ok:
            self._banner.setStyleSheet(
                "background: #e8f5e9; color: #2e7d32; padding: 6px;"
            )
        else:
            self._banner.setStyleSheet(
                "background: #fff3cd; color: #856404; padding: 6px;"
            )
        self._banner.setVisible(True)

    def _hide_banner(self) -> None:
        self._banner.setVisible(False)
