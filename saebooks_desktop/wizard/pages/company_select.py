"""First-run wizard — Page 4: Company selection.

Fetches ``GET /api/v1/companies`` with the just-obtained token.  If exactly
one company is returned the page is skipped (``skip_if_single`` behaviour
implemented via ``initializePage`` + ``wizard().next()``).  Otherwise the
user picks from a QListWidget.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWizardPage,
)


class CompanySelectPage(QWizardPage):
    """Wizard page for choosing which company to work in."""

    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.setTitle("Select company")
        self.setSubTitle("Choose the company you want to work in.")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(10)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list)

        layout.addStretch()

        # (company_id, name) pairs loaded in initializePage
        self._companies: list[tuple[str, str]] = []
        self._selected_id: str = ""

    # ------------------------------------------------------------------
    # QWizardPage protocol
    # ------------------------------------------------------------------

    def isComplete(self) -> bool:
        return bool(self._selected_id)

    def initializePage(self) -> None:
        """Load companies when the page is first shown."""
        self._list.clear()
        self._companies = []
        self._selected_id = ""
        self._status_label.setText("")

        from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
        from saebooks_desktop.services.settings import (
            get_auth_token,
            get_server_url,
            set_company_id,
        )

        base_url = get_server_url() or "http://localhost:8042"
        token = get_auth_token()
        client = APIClient(base_url=base_url, token=token)

        try:
            data = client.get("/api/v1/companies")
        except (ServerOfflineError, Exception) as exc:  # noqa: BLE001
            self._status_label.setStyleSheet("color: #c62828;")
            self._status_label.setText(f"Could not load companies: {exc}")
            return

        companies: list[dict] = data if isinstance(data, list) else data.get("items", [])
        self._companies = [
            (str(c.get("id") or ""), str(c.get("name") or ""))
            for c in companies
        ]

        if len(self._companies) == 1:
            # Single company — auto-select and skip this page.
            company_id, _ = self._companies[0]
            set_company_id(company_id)
            self._selected_id = company_id
            self.completeChanged.emit()
            # Ask the wizard to advance past this page on the next event loop tick.
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self._auto_advance)
            return

        for company_id, name in self._companies:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, company_id)
            self._list.addItem(item)

        self.completeChanged.emit()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_selection_changed(self, row: int) -> None:
        if row < 0:
            self._selected_id = ""
        else:
            item = self._list.item(row)
            self._selected_id = item.data(Qt.ItemDataRole.UserRole) if item else ""

        if self._selected_id:
            from saebooks_desktop.services.settings import set_company_id
            set_company_id(self._selected_id)

        self.completeChanged.emit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _auto_advance(self) -> None:
        """Advance the wizard past this page when there is only one company."""
        wizard = self.wizard()
        if wizard is not None:
            wizard.next()
