"""First-run wizard — Page 2: Connect to server.

Two radio buttons:
  - Local server (Docker bundle) → http://localhost:8042
  - Remote server                → user-supplied URL

A "Test Connection" button probes ``GET /api/v1/healthz``.  On success the
page becomes complete and the URL is saved to QSettings.
"""
from __future__ import annotations

import httpx

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWizardPage,
)

_LOCAL_REST_URL = "http://localhost:8042"
_LOCAL_GRPC_URL = "grpc://localhost:50051"

_FIELD_SERVER_URL = "server_url"


class ServerConnectPage(QWizardPage):
    """Wizard page for selecting and testing the server URL."""

    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.setTitle("Connect to server")
        self.setSubTitle(
            "Choose how to connect to the SAE Books API server."
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(10)

        # --- Radio buttons ---
        self._radio_local = QRadioButton("Local server (Docker bundle)")
        self._radio_remote = QRadioButton("Remote server")
        self._radio_local.setChecked(True)

        self._btn_group = QButtonGroup(self)
        self._btn_group.addButton(self._radio_local)
        self._btn_group.addButton(self._radio_remote)

        layout.addWidget(self._radio_local)
        layout.addWidget(self._radio_remote)

        # --- Remote URL input ---
        url_row = QHBoxLayout()
        self._url_label = QLabel("Server URL:")
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("https://saebooks.example.com")
        self._url_input.setEnabled(False)
        url_row.addWidget(self._url_label)
        url_row.addWidget(self._url_input, 1)
        layout.addLayout(url_row)

        # --- Test connection button + status ---
        test_row = QHBoxLayout()
        self._test_btn = QPushButton("Test Connection")
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        test_row.addWidget(self._test_btn)
        test_row.addWidget(self._status_label, 1)
        layout.addLayout(test_row)

        layout.addStretch()

        # Register a virtual field so QWizard can read the URL from other pages.
        # We manage completion manually via _connection_ok.
        self._connection_ok = False

        # Connections
        self._radio_local.toggled.connect(self._on_mode_changed)
        self._radio_remote.toggled.connect(self._on_mode_changed)
        self._url_input.textChanged.connect(self._on_url_changed)
        self._test_btn.clicked.connect(self._on_test_clicked)

    # ------------------------------------------------------------------
    # QWizardPage protocol
    # ------------------------------------------------------------------

    def isComplete(self) -> bool:
        return self._connection_ok

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    def resolved_url(self) -> str:
        """Return the URL that was successfully tested."""
        if self._radio_local.isChecked():
            return _LOCAL_REST_URL
        return self._url_input.text().strip().rstrip("/")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_mode_changed(self) -> None:
        is_remote = self._radio_remote.isChecked()
        self._url_input.setEnabled(is_remote)
        self._connection_ok = False
        self._status_label.setText("")
        self.completeChanged.emit()

    def _on_url_changed(self) -> None:
        self._connection_ok = False
        self._status_label.setText("")
        self.completeChanged.emit()

    def _on_test_clicked(self) -> None:
        url = self.resolved_url()
        if not url:
            self._set_status(False, "Please enter a server URL.")
            return

        self._test_btn.setEnabled(False)
        self._set_status(None, "Testing…")

        try:
            healthz_url = url.rstrip("/") + "/api/v1/healthz"
            with httpx.Client(timeout=5.0) as c:
                r = c.get(healthz_url)
            ok = r.status_code == 200
        except httpx.TransportError as exc:
            self._set_status(False, f"Could not reach server: {exc}")
            self._test_btn.setEnabled(True)
            return
        except Exception as exc:  # noqa: BLE001
            self._set_status(False, f"Unexpected error: {exc}")
            self._test_btn.setEnabled(True)
            return

        if ok:
            self._set_status(True, "Connection successful.")
            self._connection_ok = True
            # Persist immediately so Sign-in page can use it.
            self._save_url(url)
        else:
            self._set_status(
                False,
                f"Server responded with HTTP {r.status_code} — is the API running?",
            )

        self._test_btn.setEnabled(True)
        self.completeChanged.emit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, ok: bool | None, message: str) -> None:
        if ok is True:
            colour = "#2e7d32"
        elif ok is False:
            colour = "#c62828"
        else:
            colour = "#555"
        self._status_label.setStyleSheet(f"color: {colour};")
        self._status_label.setText(message)

    def _save_url(self, url: str) -> None:
        from saebooks_desktop.services.settings import set_grpc_url, set_server_url

        set_server_url(url)
        if self._radio_local.isChecked():
            set_grpc_url(_LOCAL_GRPC_URL)
        else:
            # Derive gRPC URL from REST URL — replace http(s) scheme with grpc.
            grpc = url.replace("https://", "grpc://").replace("http://", "grpc://")
            set_grpc_url(grpc)
