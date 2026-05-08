"""First-run wizard — Page 2: Connect to server.

Three transport modes, each suited to a different deployment shape:

1. **Local Docker** (default)
   The user is running the bundled compose stack on the same machine.
   We auto-fill ``http://localhost:8042`` for REST and ``localhost:50051``
   for gRPC, prefer gRPC, and just probe both ports.

2. **Cloud / Remote URL**
   The user is connecting to a hosted server reached over a public URL.
   Cloud reverse proxies (Caddy, nginx, Cloudflare, fly.io, etc.) almost
   always terminate HTTP/2 themselves and don't pass gRPC frames through
   transparently — so this mode is **REST only** and the user is told as
   much.  This is the path for "I run SAE Books on my Hetzner box and put
   it behind Caddy with TLS."

3. **LAN (REST + gRPC)**
   The user has a self-hosted server reachable over the local network on
   raw ports.  Both transports work.  We prefer gRPC because it's
   measurably faster for list and watch operations, and we tell the user
   so via an inline note — that's the design intent: persuade LAN users
   onto gRPC for the better experience.

The page persists four QSettings values via ``services.settings``:

- ``saebooks/server/rest_url`` — REST base URL (always set)
- ``saebooks/server/grpc_url`` — gRPC base URL (set in local + LAN modes)
- ``saebooks/server/transport_mode`` — one of ``local``/``cloud``/``lan``
- ``saebooks/server/prefer_grpc`` — bool (True for local + LAN, False for cloud)

Plus, for compatibility with the existing transport-selector path used by
``APIClient.resolve_transport()``, the resolved choice is mirrored into
``transport/mode`` (AUTO / GRPC / REST) so that ``api_client.py`` picks up
the right backend on next start.
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx

from PySide6.QtWidgets import (
    QButtonGroup,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWizardPage,
)

logger = logging.getLogger(__name__)

# Defaults for the local-docker mode.
_LOCAL_REST_URL = "http://localhost:8042"
_LOCAL_GRPC_HOST = "localhost"
_LOCAL_GRPC_PORT = 50051

# Defaults for the LAN mode — the user edits these.
_LAN_DEFAULT_REST = "http://<server>:8042"
_LAN_DEFAULT_GRPC = "<server>:50051"


class ServerConnectPage(QWizardPage):
    """Wizard page for selecting and testing the server transport."""

    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.setTitle("Connect to server")
        self.setSubTitle(
            "Choose how this desktop client will reach the SAE Books API."
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(8)

        # ------------------------------------------------------------------
        # Mode radios
        # ------------------------------------------------------------------
        self._radio_local = QRadioButton(
            "Local Docker (this machine, default for self-host bundle)"
        )
        self._radio_cloud = QRadioButton(
            "Cloud / hosted URL (REST only — recommended for public servers)"
        )
        self._radio_lan = QRadioButton(
            "LAN server (REST + gRPC available, gRPC preferred)"
        )
        self._radio_local.setChecked(True)

        # Keep the legacy attribute name pointing at the new "cloud" radio
        # so existing code/tests that still reference ``_radio_remote`` keep
        # working — it's the same conceptual role (user-supplied URL).
        self._radio_remote = self._radio_cloud

        self._btn_group = QButtonGroup(self)
        self._btn_group.addButton(self._radio_local)
        self._btn_group.addButton(self._radio_cloud)
        self._btn_group.addButton(self._radio_lan)

        layout.addWidget(self._radio_local)
        layout.addWidget(self._radio_cloud)
        layout.addWidget(self._radio_lan)

        # ------------------------------------------------------------------
        # Cloud-mode input — single REST URL
        # ------------------------------------------------------------------
        self._cloud_frame = QFrame()
        cloud_layout = QFormLayout(self._cloud_frame)
        cloud_layout.setContentsMargins(20, 4, 0, 4)
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("https://saebooks.example.com")
        cloud_layout.addRow("Server URL:", self._url_input)
        layout.addWidget(self._cloud_frame)

        # ------------------------------------------------------------------
        # LAN-mode input — gRPC host:port + REST URL + persuasion note
        # ------------------------------------------------------------------
        self._lan_frame = QFrame()
        lan_layout = QFormLayout(self._lan_frame)
        lan_layout.setContentsMargins(20, 4, 0, 4)

        self._lan_grpc_input = QLineEdit()
        self._lan_grpc_input.setPlaceholderText("books.lan:50051")
        lan_layout.addRow("gRPC host:port:", self._lan_grpc_input)

        self._lan_rest_input = QLineEdit()
        self._lan_rest_input.setPlaceholderText("http://books.lan:8042")
        lan_layout.addRow("REST URL (fallback):", self._lan_rest_input)

        self._lan_note = QLabel(
            "💡  gRPC is significantly faster than REST for list and "
            "live-update operations on the LAN — typically 3–5× lower "
            "latency and uses long-lived streaming for change events. "
            "You'll feel the difference on large ledgers. We recommend "
            "leaving gRPC as the preferred transport."
        )
        self._lan_note.setWordWrap(True)
        self._lan_note.setStyleSheet(
            "color: #1565c0; background: #e3f2fd; "
            "border-left: 3px solid #1565c0; padding: 8px; margin-top: 6px;"
        )
        lan_layout.addRow(self._lan_note)

        layout.addWidget(self._lan_frame)

        # ------------------------------------------------------------------
        # Test connection row
        # ------------------------------------------------------------------
        test_row = QHBoxLayout()
        self._test_btn = QPushButton("Test Connection")
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        test_row.addWidget(self._test_btn)
        test_row.addWidget(self._status_label, 1)
        layout.addLayout(test_row)

        layout.addStretch()

        # ------------------------------------------------------------------
        # State
        # ------------------------------------------------------------------
        self._connection_ok = False

        # Connections
        self._radio_local.toggled.connect(self._on_mode_changed)
        self._radio_cloud.toggled.connect(self._on_mode_changed)
        self._radio_lan.toggled.connect(self._on_mode_changed)
        self._url_input.textChanged.connect(self._on_input_changed)
        self._lan_grpc_input.textChanged.connect(self._on_input_changed)
        self._lan_rest_input.textChanged.connect(self._on_input_changed)
        self._test_btn.clicked.connect(self._on_test_clicked)

        # Initial visibility/enabled state
        self._on_mode_changed()

    # ------------------------------------------------------------------
    # QWizardPage protocol
    # ------------------------------------------------------------------

    def isComplete(self) -> bool:
        return self._connection_ok

    # ------------------------------------------------------------------
    # Properties used by tests + downstream pages
    # ------------------------------------------------------------------

    def selected_mode(self) -> str:
        """Return the active transport mode string ('local'|'cloud'|'lan')."""
        if self._radio_local.isChecked():
            return "local"
        if self._radio_cloud.isChecked():
            return "cloud"
        return "lan"

    def resolved_url(self) -> str:
        """Return the REST URL that will be persisted (without trailing slash)."""
        mode = self.selected_mode()
        if mode == "local":
            return _LOCAL_REST_URL
        if mode == "cloud":
            return self._url_input.text().strip().rstrip("/")
        # LAN
        return self._lan_rest_input.text().strip().rstrip("/")

    def resolved_grpc_target(self) -> tuple[str, int] | None:
        """Return (host, port) for gRPC, or None if this mode doesn't use gRPC."""
        mode = self.selected_mode()
        if mode == "cloud":
            return None
        if mode == "local":
            return (_LOCAL_GRPC_HOST, _LOCAL_GRPC_PORT)
        # LAN
        raw = self._lan_grpc_input.text().strip()
        if not raw:
            return None
        host, _, port_s = raw.partition(":")
        if not host:
            return None
        try:
            port = int(port_s) if port_s else _LOCAL_GRPC_PORT
        except ValueError:
            return None
        return (host, port)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_mode_changed(self) -> None:
        mode = self.selected_mode()
        self._cloud_frame.setVisible(mode == "cloud")
        self._lan_frame.setVisible(mode == "lan")
        self._connection_ok = False
        self._status_label.setText("")
        self.completeChanged.emit()

    def _on_input_changed(self) -> None:
        self._connection_ok = False
        self._status_label.setText("")
        self.completeChanged.emit()

    def _on_test_clicked(self) -> None:
        mode = self.selected_mode()
        rest_url = self.resolved_url()

        # Sanity-check the inputs first.
        if mode == "cloud" and not rest_url:
            self._set_status(False, "Please enter a server URL.")
            return
        if mode == "lan":
            if not rest_url:
                self._set_status(False, "Please enter the REST URL for the LAN server.")
                return
            if self.resolved_grpc_target() is None:
                self._set_status(
                    False,
                    "Please enter the gRPC host:port for the LAN server.",
                )
                return

        self._test_btn.setEnabled(False)
        self._set_status(None, "Testing…")

        # 1. REST probe — required in every mode (cloud has nothing else;
        #    local and LAN use REST as the fallback transport).
        rest_ok, rest_msg = self._probe_rest(rest_url)
        if not rest_ok:
            self._set_status(False, rest_msg)
            self._test_btn.setEnabled(True)
            return

        # 2. gRPC probe — only relevant when the mode supports it.
        grpc_ok = False
        grpc_msg = ""
        if mode in ("local", "lan"):
            target = self.resolved_grpc_target()
            if target is not None:
                grpc_ok, grpc_msg = self._probe_grpc(target[0], target[1])

        # 3. Compose status + persist.
        if mode == "cloud":
            status = "Connected via REST. (Cloud mode does not use gRPC.)"
        elif grpc_ok:
            status = (
                f"Connected — REST and gRPC both reachable. "
                f"gRPC will be used as the preferred transport."
            )
        else:
            status = (
                f"Connected via REST. gRPC probe failed "
                f"({grpc_msg or 'unreachable'}); REST fallback will be used."
            )

        self._set_status(True, status)
        self._connection_ok = True
        self._save_settings(mode, rest_url, grpc_ok)
        self._test_btn.setEnabled(True)
        self.completeChanged.emit()

    # ------------------------------------------------------------------
    # Probes
    # ------------------------------------------------------------------

    def _probe_rest(self, url: str) -> tuple[bool, str]:
        """GET ``/api/v1/healthz`` and return (ok, status_message)."""
        if not url:
            return False, "REST URL is empty."
        try:
            healthz = url.rstrip("/") + "/api/v1/healthz"
            with httpx.Client(timeout=5.0) as c:
                r = c.get(healthz)
        except httpx.TransportError as exc:
            return False, f"Could not reach server: {exc}"
        except Exception as exc:  # noqa: BLE001
            return False, f"Unexpected error: {exc}"

        if r.status_code == 200:
            return True, "REST OK."
        return False, (
            f"Server responded with HTTP {r.status_code} on /api/v1/healthz "
            "— is the API container running?"
        )

    def _probe_grpc(self, host: str, port: int) -> tuple[bool, str]:
        """Open a gRPC channel and call ``Heartbeat`` to confirm reachability."""
        # Imported lazily so that the wizard module loads even when grpc
        # codegen is missing on a dev machine.
        try:
            from saebooks_desktop.services.grpc_client import GrpcClient
        except Exception as exc:  # noqa: BLE001
            return False, f"gRPC stub unavailable: {exc}"

        client = None
        try:
            client = GrpcClient(host=host, port=port, auth_token="")
            ok = client.is_reachable(timeout=2.0)
            return ok, "" if ok else f"no response from {host}:{port}"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:  # noqa: BLE001
                    pass

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_settings(self, mode: str, rest_url: str, grpc_reachable: bool) -> None:
        """Write all four wizard keys + mirror the transport-mode preference."""
        from saebooks_desktop.services.settings import (
            TRANSPORT_CLOUD,
            TRANSPORT_LAN,
            TRANSPORT_LOCAL,
            set_grpc_url,
            set_prefer_grpc,
            set_server_url,
            set_transport_mode,
        )

        set_server_url(rest_url)

        if mode == "cloud":
            set_transport_mode(TRANSPORT_CLOUD)
            set_prefer_grpc(False)
            # Clear any stale gRPC URL so APIClient doesn't try to use it.
            set_grpc_url("")
            self._mirror_api_client_transport(prefer_grpc=False)
            return

        # local / LAN — both have gRPC available.
        target = self.resolved_grpc_target()
        if target is not None:
            host, port = target
            set_grpc_url(f"grpc://{host}:{port}")
        prefer = bool(grpc_reachable)  # only prefer if probe succeeded
        set_prefer_grpc(prefer)
        set_transport_mode(TRANSPORT_LOCAL if mode == "local" else TRANSPORT_LAN)
        self._mirror_api_client_transport(prefer_grpc=prefer)

    def _mirror_api_client_transport(self, prefer_grpc: bool) -> None:
        """Mirror the wizard's preference into APIClient's TransportMode key.

        ``APIClient.resolve_transport()`` reads ``transport/mode`` from
        QSettings (AUTO / GRPC / REST).  We map the wizard outcome onto
        that key so the existing transport selector picks the right
        backend without further coupling.
        """
        try:
            from saebooks_desktop.services.api_client import APIClient, TransportMode
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not mirror transport preference: %s", exc)
            return
        APIClient.set_transport(
            TransportMode.GRPC if prefer_grpc else TransportMode.REST
        )

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

    @staticmethod
    def _scheme_of(url: str) -> str:
        try:
            return urlparse(url).scheme.lower()
        except Exception:  # noqa: BLE001
            return ""
