"""Bootstrap progress dialog — shown on first run while snapshot downloads.

Displayed as a modal, non-closeable dialog with an indeterminate progress bar.
Closes automatically when the sync engine emits ``sync_completed``.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)


class BootstrapProgressDialog(QDialog):
    """Modal progress dialog for the initial snapshot download.

    Usage::

        dlg = BootstrapProgressDialog(parent=main_window)
        sync_engine.sync_completed.connect(dlg.on_sync_completed)
        dlg.exec()   # blocks until on_sync_completed closes it

    The dialog is intentionally non-closeable during the download — the user
    must wait for the first sync to complete before the app is usable.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("SAE Books — First Run Setup")
        # Remove the close button and prevent the user dismissing it.
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )
        self.setModal(True)
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        heading = QLabel("Downloading your company data\u2026")
        heading.setStyleSheet("font-size: 13pt; font-weight: bold;")
        layout.addWidget(heading)

        self._status_label = QLabel("Please wait while your data is prepared.")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # indeterminate / busy indicator
        self._progress_bar.setTextVisible(False)
        layout.addWidget(self._progress_bar)

        self._count_label = QLabel("")
        self._count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._count_label.setStyleSheet("color: #666;")
        layout.addWidget(self._count_label)

    # ------------------------------------------------------------------
    # Public API — connect to SyncEngine signals
    # ------------------------------------------------------------------

    @Slot(int)
    def on_progress(self, n_loaded: int) -> None:
        """Update the record count label.  Connect to a progress signal."""
        self._count_label.setText(f"{n_loaded:,} records loaded")

    @Slot(int)
    def on_sync_completed(self, n: int) -> None:
        """Called when bootstrap finishes — updates label and closes."""
        self._count_label.setText(f"{n:,} records loaded")
        self._status_label.setText("Setup complete. Opening SAE Books\u2026")
        # Use accept() so callers can distinguish normal close from reject.
        self.accept()
