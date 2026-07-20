"""Full-accounting doorway — the single upgrade path out of cashbook mode.

Per the adjudicated navigation verdict (revises PoC decision #16):
cashbook-mode navigation carries exactly ONE "Full accounting →" item.
It opens this explainer rather than flipping the mode on click — the
user owns a complete double-entry ledger already (cashbook entries are
real journal entries), so the upgrade is lossless and nothing is
re-keyed. The Upgrade button confirms, then calls the engine's
``POST /api/v1/companies/{id}/bookkeeping-mode`` with ``mode="full"``
(``upgrade_cashbook_to_full`` on the engine side).

Signals:
    upgraded() — emitted after a successful upgrade; MainWindow
        re-renders the navigation for full mode.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.api_client import (
    APIClient,
    APIError,
    ServerOfflineError,
)
from saebooks_desktop.services.cashbook import set_bookkeeping_mode
from saebooks_desktop.services.settings import get_company_id

_EXPLAINER_TEXT = (
    "You already own a complete double-entry ledger.\n\n"
    "Every cashbook entry you have recorded is a real journal entry in "
    "that ledger — the cashbook is just a simpler window onto it.\n\n"
    "Switch on the full accounting suite anytime: invoices, bills, "
    "contacts, bank reconciliation, reports and more. Nothing is "
    "re-keyed, nothing is migrated, and nothing is lost — your existing "
    "entries stay exactly where they are."
)


class FullAccountingDoorView(QWidget):
    """Explainer + upgrade action for switching a cashbook company to full mode."""

    upgraded = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._client = APIClient()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(16)

        title = QLabel("Full accounting")
        title.setObjectName("door_title")
        title.setStyleSheet("font-size: 20pt; font-weight: bold;")
        layout.addWidget(title)

        body = QLabel(_EXPLAINER_TEXT)
        body.setObjectName("door_body")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(body)

        self._error_label = QLabel("")
        self._error_label.setObjectName("door_error")
        self._error_label.setWordWrap(True)
        self._error_label.setStyleSheet("color: #c62828;")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        btn_row = QHBoxLayout()
        self._upgrade_btn = QPushButton("Switch to full accounting")
        self._upgrade_btn.setObjectName("upgrade_btn")
        self._upgrade_btn.clicked.connect(self._on_upgrade_clicked)
        btn_row.addWidget(self._upgrade_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_upgrade_clicked(self) -> None:
        self._error_label.setVisible(False)

        company_id = get_company_id()
        if not company_id:
            self._show_error("No company is selected.")
            return

        confirm = QMessageBox.question(
            self,
            "Switch to full accounting",
            "Switch this company to the full accounting suite?\n\n"
            "This is lossless — your cashbook entries are already real "
            "journal entries and nothing is re-keyed. You can switch back "
            "to cashbook mode later from Settings.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            set_bookkeeping_mode(self._client, company_id, "full")
        except ServerOfflineError:
            self._show_error("Cannot switch — server is offline.")
            return
        except APIError as exc:
            # Surface the engine's error message on refusal.
            self._show_error(f"Switch failed: {exc}")
            return

        self.upgraded.emit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)
