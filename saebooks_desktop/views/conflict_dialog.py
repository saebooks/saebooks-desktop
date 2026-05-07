"""Conflict resolution dialog — shown when a 409 is returned from outbox drain.

Layout::

    ┌─────────────────────────────────────────────────────────┐
    │  Sync Conflict                                          │
    │                                                         │
    │  This contact was changed on the server while you       │
    │  were offline.                                          │
    │                                                         │
    │  ┌─────────────────────┐  ┌──────────────────────────┐ │
    │  │  Server version     │  │  Your version            │ │
    │  │  { ... JSON ... }   │  │  { ... JSON ... }        │ │
    │  └─────────────────────┘  └──────────────────────────┘ │
    │                                                         │
    │  [Keep Server Version]  [Keep My Version]  [Cancel]    │
    └─────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Resolution constants stored to the conflicts table.
RESOLUTION_KEEP_SERVER = "keep_server"
RESOLUTION_KEEP_LOCAL = "keep_local"


def _pretty_json(obj: Any) -> str:
    """Return a pretty-printed JSON string from a dict (or raw string)."""
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except json.JSONDecodeError:
            return obj
    return json.dumps(obj, indent=2, ensure_ascii=False)


def _field_summary(obj: Any) -> str:
    """Return a one-line summary of the top-level fields in *obj*."""
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except json.JSONDecodeError:
            return obj[:120]
    if not isinstance(obj, dict):
        return str(obj)[:120]
    pairs = []
    for k, v in list(obj.items())[:5]:
        pairs.append(f"{k}: {v!r}")
    summary = ", ".join(pairs)
    if len(obj) > 5:
        summary += f", +{len(obj) - 5} more"
    return summary


class ConflictDialog(QDialog):
    """Modal conflict resolution dialog.

    Args:
        entity: Entity type string (e.g. ``"contact"``).
        entity_id: Entity primary key string.
        server_data: Current server version (dict or JSON string).
        local_data: The version from the outbox (what the user edited).
        parent: Optional Qt parent widget.

    After ``exec()`` the caller should inspect ``result()``:
    - ``QDialog.Accepted`` — user clicked Keep Server or Keep Mine.
      Check ``resolution`` attribute for which one.
    - ``QDialog.Rejected`` — user clicked Cancel.

    The ``resolution`` attribute is one of:
    - ``RESOLUTION_KEEP_SERVER``
    - ``RESOLUTION_KEEP_LOCAL``
    - ``None`` (cancelled)
    """

    def __init__(
        self,
        entity: str,
        entity_id: str,
        server_data: Any,
        local_data: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sync Conflict")
        self.setMinimumSize(620, 460)
        self.setModal(True)

        self.resolution: str | None = None

        self._entity = entity
        self._entity_id = entity_id
        self._server_data = server_data
        self._local_data = local_data

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Description label
        desc = QLabel(
            f"This <b>{entity}</b> was changed on the server while you were offline."
            "<br><br>"
            f"<b>Server version:</b> {_field_summary(server_data)}<br>"
            f"<b>Your version:</b> {_field_summary(local_data)}"
        )
        desc.setWordWrap(True)
        desc.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(desc)

        # Side-by-side diff panes
        panes_widget = QWidget()
        panes_layout = QHBoxLayout(panes_widget)
        panes_layout.setContentsMargins(0, 0, 0, 0)
        panes_layout.setSpacing(8)

        server_label = QLabel("<b>Server version</b>")
        local_label = QLabel("<b>Your version</b>")

        self._server_pane = QTextEdit()
        self._server_pane.setReadOnly(True)
        self._server_pane.setPlainText(_pretty_json(server_data))
        self._server_pane.setStyleSheet(
            "background: #fff8f0; font-family: monospace; font-size: 9pt;"
        )

        self._local_pane = QTextEdit()
        self._local_pane.setReadOnly(True)
        self._local_pane.setPlainText(_pretty_json(local_data))
        self._local_pane.setStyleSheet(
            "background: #f0f8ff; font-family: monospace; font-size: 9pt;"
        )

        server_col = QVBoxLayout()
        server_col.addWidget(server_label)
        server_col.addWidget(self._server_pane)

        local_col = QVBoxLayout()
        local_col.addWidget(local_label)
        local_col.addWidget(self._local_pane)

        panes_layout.addLayout(server_col)
        panes_layout.addLayout(local_col)
        layout.addWidget(panes_widget, 1)

        # Buttons
        btn_box = QWidget()
        btn_layout = QHBoxLayout(btn_box)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        self._keep_server_btn = QPushButton("Keep Server Version")
        self._keep_server_btn.setDefault(False)
        self._keep_server_btn.clicked.connect(self._on_keep_server)

        self._keep_local_btn = QPushButton("Keep My Version")
        self._keep_local_btn.clicked.connect(self._on_keep_local)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self._keep_server_btn)
        btn_layout.addWidget(self._keep_local_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self._cancel_btn)

        layout.addWidget(btn_box)

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_keep_server(self) -> None:
        self.resolution = RESOLUTION_KEEP_SERVER
        self.accept()

    def _on_keep_local(self) -> None:
        self.resolution = RESOLUTION_KEEP_LOCAL
        self.accept()
