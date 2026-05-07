"""Global search view.

Provides a simple search widget: QLineEdit at top, QListWidget below showing
results from ``GET /api/v1/search?q=...``.

The API response is expected to be ``{"results": [{type, id, label, detail}]}``.

Signals:
  - ``result_selected(type: str, id: str)`` — emitted on double-click with the
    result type and id.  MainWindow wires this to navigate to the appropriate
    section.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.api_client import APIClient, ServerOfflineError

# UserRole stores a tuple (type_str, id_str) encoded as "<type>:<id>"
_ROLE_KEY = Qt.ItemDataRole.UserRole


def _encode_key(result_type: str, result_id: str) -> str:
    return f"{result_type}:{result_id}"


def _decode_key(key: str) -> tuple[str, str]:
    parts = key.split(":", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return key, ""


class SearchView(QWidget):
    """Global search view.

    Fetches results from ``GET /api/v1/search?q=<query>`` and displays them
    in a QListWidget.  Double-clicking emits ``result_selected(type, id)``.
    """

    result_selected = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._client = APIClient()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search invoices, contacts, accounts…")
        self._search_edit.setMinimumHeight(30)
        self._search_edit.returnPressed.connect(self._on_search)
        self._search_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._search_edit)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #888; font-size: 10pt;")
        layout.addWidget(self._status_label)

        self._results_list = QListWidget()
        self._results_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._results_list, 1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def focus_search(self) -> None:
        """Focus and select-all the search field — call when opening the view."""
        self._search_edit.setFocus()
        self._search_edit.selectAll()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _on_text_changed(self, text: str) -> None:
        if not text.strip():
            self._results_list.clear()
            self._status_label.setText("")

    def _on_search(self) -> None:
        query = self._search_edit.text().strip()
        if not query:
            return
        self._results_list.clear()
        self._status_label.setText("Searching…")
        try:
            data = self._client.get("/api/v1/search", params={"q": query})
        except ServerOfflineError:
            self._status_label.setText("Server offline — search unavailable.")
            return
        except Exception:  # noqa: BLE001
            self._status_label.setText("Search failed.")
            return
        results: list[dict[str, Any]] = data.get("results", [])
        if not results:
            self._status_label.setText("No results.")
            return
        self._status_label.setText(f"{len(results)} result(s)")
        for r in results:
            label = r.get("label") or ""
            detail = r.get("detail") or ""
            display = f"{label}  —  {detail}" if detail else label
            item = QListWidgetItem(display)
            item.setData(_ROLE_KEY, _encode_key(r.get("type") or "", r.get("id") or ""))
            self._results_list.addItem(item)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        key = item.data(_ROLE_KEY) or ""
        result_type, result_id = _decode_key(key)
        if result_type and result_id:
            self.result_selected.emit(result_type, result_id)
