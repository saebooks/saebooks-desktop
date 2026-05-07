"""Contacts view — QWidget with QTableView showing contacts from the API.

Offline behaviour
-----------------
- On initial load: attempt API fetch; if the server is offline, fall back
  to the local SQLite ``entity_cache`` immediately (zero latency).
- The "New Contact" button now enqueues the operation to the outbox
  (optimistic UI) rather than showing a "Not implemented" dialog.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.api_client import APIClient, ServerOfflineError


_COLUMNS = ["Name", "Email", "Phone"]


class ContactsView(QWidget):
    """Contacts list — shows contacts loaded from /api/v1/contacts.

    Falls back to the local SQLite entity_cache when the server is offline.
    "New Contact" enqueues to the outbox and optimistically adds to the table.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._client = APIClient()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self.load_contacts)
        self._new_btn = QPushButton("New Contact")
        self._new_btn.clicked.connect(self._on_new_contact)
        toolbar.addWidget(self._refresh_btn)
        toolbar.addWidget(self._new_btn)
        layout.addWidget(toolbar)

        # Offline banner (hidden by default)
        self._offline_label = QLabel(
            "Server offline — showing cached data"
        )
        self._offline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._offline_label.setStyleSheet(
            "background: #fff3cd; color: #856404; padding: 4px;"
        )
        self._offline_label.setVisible(False)
        layout.addWidget(self._offline_label)

        # Table
        self._model = QStandardItemModel(0, len(_COLUMNS))
        self._model.setHorizontalHeaderLabels(_COLUMNS)

        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

        self.load_contacts()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_contacts(self) -> None:
        """Fetch contacts from the API; fall back to SQLite cache if offline."""
        self._offline_label.setVisible(False)
        try:
            data = self._client.get("/api/v1/contacts", params={"limit": 200})
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._show_offline_with_cache()
            return

        items: list[dict[str, Any]] = data.get("items", [])
        self._populate(items)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _populate(self, contacts: list[dict[str, Any]]) -> None:
        self._model.removeRows(0, self._model.rowCount())
        for row, c in enumerate(contacts):
            self._model.insertRow(row)
            self._model.setItem(row, 0, QStandardItem(c.get("name", "")))
            self._model.setItem(row, 1, QStandardItem(c.get("email") or ""))
            self._model.setItem(row, 2, QStandardItem(c.get("phone") or ""))

    def _show_offline_with_cache(self) -> None:
        """Show offline banner and populate from local SQLite entity_cache."""
        self._offline_label.setVisible(True)

        try:
            from saebooks_desktop.cache.db import get_connection, init_db

            conn = get_connection()
            init_db(conn)
            try:
                rows = conn.execute(
                    "SELECT data FROM entity_cache WHERE entity = 'contact'"
                ).fetchall()
                contacts = [json.loads(r["data"]) for r in rows]
                self._populate(contacts)
            finally:
                conn.close()
        except Exception:  # noqa: BLE001
            # Cache read failed — leave whatever was in the table previously.
            pass

    def _on_new_contact(self) -> None:
        """Prompt for minimal contact details and enqueue to the outbox.

        Optimistically adds the new contact to the visible table even before
        the server confirms.  The outbox drain will replay the operation when
        back online.
        """
        name, ok = QInputDialog.getText(self, "New Contact", "Contact name:")
        if not ok or not name.strip():
            return

        name = name.strip()
        idempotency_key = str(uuid.uuid4())
        body = {"name": name}

        try:
            from saebooks_desktop.cache.outbox import enqueue

            enqueue(
                method="POST",
                path="/api/v1/contacts",
                body=body,
                idempotency_key=idempotency_key,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(
                self,
                "Outbox error",
                f"Could not queue new contact: {exc}",
            )
            return

        # Optimistic UI — add to table immediately.
        row = self._model.rowCount()
        self._model.insertRow(row)
        self._model.setItem(row, 0, QStandardItem(name))
        self._model.setItem(row, 1, QStandardItem(""))
        self._model.setItem(row, 2, QStandardItem(""))
