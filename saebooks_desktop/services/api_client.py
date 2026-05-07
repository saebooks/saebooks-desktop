"""httpx-based synchronous API client for saebooks-api.

Reads SAEBOOKS_API_URL + SAEBOOKS_API_TOKEN from env (priority) or
QSettings (fallback) so the app works without a GUI settings dialog during
development.

Design note: synchronous httpx is intentional here. Qt runs on the main
thread and mixing asyncio with Qt's own event loop adds significant
complexity for negligible benefit at this stage. Long-running calls should
be dispatched via QThread or QRunnable (not yet implemented — deferred to
Phase 4.5 sync engine).

Transport selection
-------------------
``TransportMode`` controls which backend is used for API calls:

- ``AUTO``  (default): probe gRPC; use it if reachable, else fall back to REST.
- ``GRPC``:  force gRPC. If unreachable a warning is logged and REST is used.
- ``REST``:  force REST (httpx).

The resolved transport is cached per-session in ``_active_transport``.  Call
``resolve_transport()`` on an ``APIClient`` instance to obtain the active
transport object (either ``GrpcClient`` or ``APIClient`` itself for REST).
Use ``set_transport(mode)`` to persist a preference to QSettings.
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any

import httpx

from saebooks_desktop.settings import get_api_token, get_api_url

logger = logging.getLogger(__name__)

_TRANSPORT_QSETTINGS_KEY = "transport/mode"


class TransportMode(Enum):
    """Transport backend selection mode."""

    GRPC = "GRPC"
    REST = "REST"
    AUTO = "AUTO"


class APIError(Exception):
    """Raised when the API returns a non-2xx response or is unreachable."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ServerOfflineError(APIError):
    """Raised when the server is unreachable (network error, refused, timeout)."""


class APIClient:
    """Thin synchronous wrapper around httpx for saebooks-api.

    Also acts as the transport selector — call ``resolve_transport()`` to get
    the best available transport for this session.
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = (base_url or get_api_url()).rstrip("/")
        self._token = token or get_api_token()
        self._timeout = timeout
        # Cached after first resolve_transport() call.
        self._active_transport: "APIClient | GrpcClient | None" = None  # type: ignore[name-defined]

    # ------------------------------------------------------------------
    # Transport selector
    # ------------------------------------------------------------------

    def resolve_transport(self) -> "APIClient | GrpcClient":  # type: ignore[name-defined]
        """Return the active transport for this session.

        On first call, reads ``QSettings("transport/mode")`` (default AUTO) and:

        - ``AUTO``: tries ``GrpcClient.is_reachable()``; uses gRPC if True, else REST.
        - ``GRPC``: forces gRPC; logs a warning and falls back to REST if unreachable.
        - ``REST``: returns ``self`` (this REST client).

        The result is cached in ``_active_transport`` for the session lifetime.
        """
        if self._active_transport is not None:
            return self._active_transport

        mode = _read_transport_mode()

        if mode == TransportMode.REST:
            self._active_transport = self
            return self._active_transport

        # Build a gRPC client to probe.
        grpc_client = _make_grpc_client(self._token)

        if mode == TransportMode.GRPC:
            if grpc_client.is_reachable():
                self._active_transport = grpc_client
            else:
                logger.warning(
                    "Transport mode is GRPC but server is unreachable on %s; "
                    "falling back to REST.",
                    grpc_client._target,
                )
                self._active_transport = self
            return self._active_transport

        # AUTO: probe gRPC and decide.
        if grpc_client.is_reachable():
            self._active_transport = grpc_client
        else:
            self._active_transport = self
        return self._active_transport

    @property
    def active_transport_name(self) -> str:
        """Human-readable label for the active transport: 'gRPC' or 'REST'."""
        if self._active_transport is None:
            return "REST"  # not yet resolved — default label
        from saebooks_desktop.services.grpc_client import GrpcClient

        return "gRPC" if isinstance(self._active_transport, GrpcClient) else "REST"

    # ------------------------------------------------------------------
    # Transport persistence
    # ------------------------------------------------------------------

    @staticmethod
    def set_transport(mode: TransportMode) -> None:
        """Persist the transport mode preference to QSettings."""
        from PySide6.QtCore import QSettings

        s = QSettings("SAE Engineering", "SAE Books")
        s.setValue(_TRANSPORT_QSETTINGS_KEY, mode.value)
        s.sync()

    # ------------------------------------------------------------------
    # REST helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self._base_url,
            headers=self._headers(),
            timeout=self._timeout,
        )

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET *path* and return the parsed JSON body.

        Raises:
            ServerOfflineError: if the server is unreachable.
            APIError: for non-2xx HTTP responses.
        """
        try:
            with self._client() as c:
                r = c.get(path, params=params)
        except httpx.TransportError as exc:
            raise ServerOfflineError(f"Server unreachable: {exc}") from exc
        if not r.is_success:
            raise APIError(
                f"GET {path} returned {r.status_code}: {r.text[:200]}",
                status_code=r.status_code,
            )
        return r.json()

    def post(
        self,
        path: str,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """POST *path* with a JSON body and return the parsed JSON response."""
        try:
            with self._client() as c:
                r = c.post(path, json=json, headers=headers or {})
        except httpx.TransportError as exc:
            raise ServerOfflineError(f"Server unreachable: {exc}") from exc
        if not r.is_success:
            raise APIError(
                f"POST {path} returned {r.status_code}: {r.text[:200]}",
                status_code=r.status_code,
            )
        return r.json()

    def patch(
        self,
        path: str,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, Any]:
        """PATCH *path* and return (status_code, parsed_json).

        Returns the status code rather than raising on 409 so callers can
        handle conflict resolution themselves.
        """
        try:
            with self._client() as c:
                r = c.patch(path, json=json, headers=headers or {})
        except httpx.TransportError as exc:
            raise ServerOfflineError(f"Server unreachable: {exc}") from exc
        if r.status_code == 409:
            return r.status_code, r.json()
        if not r.is_success:
            raise APIError(
                f"PATCH {path} returned {r.status_code}: {r.text[:200]}",
                status_code=r.status_code,
            )
        return r.status_code, r.json()

    def delete(self, path: str) -> int:
        """DELETE *path* and return the HTTP status code.

        Raises:
            ServerOfflineError: if the server is unreachable.
            APIError: for non-2xx (and non-404) HTTP responses.
        """
        try:
            with self._client() as c:
                r = c.delete(path)
        except httpx.TransportError as exc:
            raise ServerOfflineError(f"Server unreachable: {exc}") from exc
        if not r.is_success and r.status_code != 404:
            raise APIError(
                f"DELETE {path} returned {r.status_code}: {r.text[:200]}",
                status_code=r.status_code,
            )
        return r.status_code

    def get_stream(self, path: str, params: dict[str, Any] | None = None):
        """GET *path* and return an iterable of text lines (NDJSON stream).

        Uses ``stream=True`` under the hood so large responses don't buffer
        entirely in memory.  Each yielded item is a decoded text line (strip
        trailing newline yourself if needed).

        Raises:
            ServerOfflineError: if the server is unreachable.
            APIError: for non-2xx HTTP responses.
        """
        try:
            with self._client() as c:
                with c.stream("GET", path, params=params) as r:
                    if not r.is_success:
                        body = r.read().decode("utf-8", errors="replace")
                        raise APIError(
                            f"GET {path} returned {r.status_code}: {body[:200]}",
                            status_code=r.status_code,
                        )
                    yield from r.iter_lines()
        except httpx.TransportError as exc:
            raise ServerOfflineError(f"Server unreachable: {exc}") from exc

    def is_reachable(self) -> bool:
        """Quick connectivity probe — returns True if the API responds to GET /."""
        try:
            with self._client() as c:
                r = c.get("/", timeout=3.0)
            return r.status_code < 500
        except httpx.TransportError:
            return False


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _read_transport_mode() -> TransportMode:
    """Read transport mode from QSettings, defaulting to AUTO."""
    try:
        from PySide6.QtCore import QSettings

        s = QSettings("SAE Engineering", "SAE Books")
        raw = s.value(_TRANSPORT_QSETTINGS_KEY, TransportMode.AUTO.value)
        return TransportMode(str(raw))
    except Exception:  # noqa: BLE001
        return TransportMode.AUTO


def _make_grpc_client(token: str) -> "GrpcClient":  # type: ignore[name-defined]
    """Construct a GrpcClient using the default host/port."""
    import os

    from saebooks_desktop.services.grpc_client import GrpcClient

    host = os.environ.get("SAEBOOKS_GRPC_HOST", "localhost")
    port = int(os.environ.get("SAEBOOKS_GRPC_PORT", str(50051)))
    return GrpcClient(host=host, port=port, auth_token=token)


def get_transport(token: str | None = None) -> "APIClient | GrpcClient":  # type: ignore[name-defined]
    """Module-level factory: return the resolved transport for this session.

    Convenience wrapper so SyncEngine and views don't need to instantiate
    APIClient just to call resolve_transport().
    """
    client = APIClient(token=token)
    return client.resolve_transport()
