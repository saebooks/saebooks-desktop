"""Reusable AI document extraction widget.

``DocumentExtractWidget`` renders a compact panel the caller embeds inside
a form (e.g. BillForm, InvoiceForm).  The user picks a file, clicks
Extract, and the widget fires ``extraction_complete(dict)`` when the API
returns a result.

Signals:
    extraction_complete(dict) — payload is the raw extraction result dict.

Usage::

    widget = DocumentExtractWidget(client, parent=self)
    widget.extraction_complete.connect(self._on_extraction)
    layout.insertWidget(0, widget)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.api_client import APIClient, APIError, ServerOfflineError
from saebooks_desktop.services.ai_extraction import extract_document

_LOW_CONFIDENCE_THRESHOLD = 0.70
_ORANGE_CONFIDENCE_THRESHOLD = 0.70

_FILE_FILTER = "Documents (*.pdf *.jpg *.jpeg *.png)"


class DocumentExtractWidget(QWidget):
    """Browse + extract panel for AI document data extraction.

    Embeds as a collapsed QGroupBox-style section.  After the user picks a
    file and clicks Extract, the widget calls the API synchronously on the
    main thread (consistent with the rest of the service layer) then emits
    ``extraction_complete``.

    Error states are displayed inline so the surrounding form is not
    disrupted.
    """

    extraction_complete = Signal(dict)

    def __init__(
        self,
        client: APIClient,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._file_path: Path | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # --- Controls row ---
        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)

        self._browse_btn = QPushButton("Browse\u2026")
        self._browse_btn.setFixedWidth(80)
        self._browse_btn.clicked.connect(self._on_browse)
        controls_layout.addWidget(self._browse_btn)

        self._path_label = QLabel("No file selected")
        self._path_label.setObjectName("ai_path_label")
        controls_layout.addWidget(self._path_label, 1)

        self._extract_btn = QPushButton("Extract")
        self._extract_btn.setFixedWidth(72)
        self._extract_btn.setEnabled(False)
        self._extract_btn.clicked.connect(self._on_extract)
        controls_layout.addWidget(self._extract_btn)

        layout.addWidget(controls)

        # --- Progress bar (hidden until extraction starts) ---
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        self._progress.setVisible(False)
        self._progress.setMaximumHeight(8)
        layout.addWidget(self._progress)

        # --- Confidence label (hidden until result arrives) ---
        self._confidence_label = QLabel()
        self._confidence_label.setObjectName("ai_confidence_label")
        self._confidence_label.setVisible(False)
        layout.addWidget(self._confidence_label)

        # --- Inline error label ---
        self._error_label = QLabel()
        self._error_label.setObjectName("ai_error_label")
        self._error_label.setWordWrap(True)
        self._error_label.setStyleSheet("color: #c62828;")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def selected_path(self) -> Path | None:
        """Return the currently selected file path, or None."""
        return self._file_path

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_browse(self) -> None:
        """Open a file dialog and update the path label."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select document to extract",
            "",
            _FILE_FILTER,
        )
        if not path:
            return
        self._file_path = Path(path)
        self._path_label.setText(self._file_path.name)
        self._extract_btn.setEnabled(True)
        self._error_label.setVisible(False)
        self._confidence_label.setVisible(False)

    def _on_extract(self) -> None:
        """Call the extraction API and emit the result or show an error."""
        if self._file_path is None:
            return

        self._set_busy(True)
        self._error_label.setVisible(False)
        self._confidence_label.setVisible(False)

        try:
            result = extract_document(self._client, self._file_path)
        except (ServerOfflineError, APIError, ValueError) as exc:
            self._set_busy(False)
            self._show_error(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            self._set_busy(False)
            self._show_error(f"Unexpected error: {exc}")
            return

        self._set_busy(False)
        self._show_confidence(result.get("extraction_confidence"))
        self.extraction_complete.emit(result)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _set_busy(self, busy: bool) -> None:
        self._progress.setVisible(busy)
        self._browse_btn.setEnabled(not busy)
        self._extract_btn.setEnabled(not busy and self._file_path is not None)

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    def _show_confidence(self, confidence: Any) -> None:
        """Display the confidence percentage, coloured orange if below threshold."""
        if confidence is None:
            return
        try:
            pct = float(confidence) * 100
        except (TypeError, ValueError):
            return

        self._confidence_label.setText(f"AI confidence: {pct:.0f}%")
        if float(confidence) < _LOW_CONFIDENCE_THRESHOLD:
            self._confidence_label.setStyleSheet("color: #e65100;")  # orange
        else:
            self._confidence_label.setStyleSheet("color: #2e7d32;")  # green
        self._confidence_label.setVisible(True)
