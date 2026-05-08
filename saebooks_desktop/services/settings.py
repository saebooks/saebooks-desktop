"""Wizard-facing QSettings wrapper.

Keys used by the first-run wizard and startup gate:

    saebooks/server/rest_url   — REST base URL chosen in the wizard
    saebooks/server/grpc_url   — gRPC base URL (derived or explicit)
    saebooks/auth/token        — Bearer token from login
    saebooks/auth/company_id   — Selected company UUID

``is_first_run()`` returns True when no server URL has been persisted yet.
The existing ``saebooks_desktop.settings`` module owns ``api/url`` and
``api/token``; this module stores the wizard-specific keys in a parallel
namespace and writes through to ``api/url`` / ``api/token`` so that
``APIClient`` picks them up without changes.
"""
from __future__ import annotations

import os

from PySide6.QtCore import QSettings

_ORG = "SAE Engineering"
_APP = "SAE Books"

_KEY_REST_URL = "saebooks/server/rest_url"
_KEY_GRPC_URL = "saebooks/server/grpc_url"
_KEY_TRANSPORT_MODE = "saebooks/server/transport_mode"
_KEY_PREFER_GRPC = "saebooks/server/prefer_grpc"
_KEY_TOKEN = "saebooks/auth/token"
_KEY_COMPANY_ID = "saebooks/auth/company_id"

# Mirror keys used by APIClient (saebooks_desktop.settings)
_API_URL_KEY = "api/url"
_API_TOKEN_KEY = "api/token"

# Transport mode values
TRANSPORT_LOCAL = "local"   # Local Docker bundle on this host
TRANSPORT_CLOUD = "cloud"   # Customer's hosted server reached over public URL
TRANSPORT_LAN = "lan"       # On-prem server on the same LAN as this client

_VALID_TRANSPORTS = {TRANSPORT_LOCAL, TRANSPORT_CLOUD, TRANSPORT_LAN}


def _s() -> QSettings:
    return QSettings(_ORG, _APP)


# ---------------------------------------------------------------------------
# Server URL
# ---------------------------------------------------------------------------


def get_server_url() -> str:
    """Return the persisted REST server URL, or '' if not set."""
    if env := os.environ.get("SAEBOOKS_API_URL"):
        return env.rstrip("/")
    s = _s()
    return str(s.value(_KEY_REST_URL, "")).rstrip("/")


def set_server_url(url: str) -> None:
    """Persist the REST server URL and keep api/url in sync."""
    clean = url.rstrip("/")
    s = _s()
    s.setValue(_KEY_REST_URL, clean)
    # Keep APIClient's key in sync so existing code reads the right URL.
    s.setValue(_API_URL_KEY, clean)
    s.sync()


def get_grpc_url() -> str:
    """Return the persisted gRPC URL, or '' if not set."""
    s = _s()
    return str(s.value(_KEY_GRPC_URL, "")).rstrip("/")


def set_grpc_url(url: str) -> None:
    s = _s()
    s.setValue(_KEY_GRPC_URL, url.rstrip("/"))
    s.sync()


# ---------------------------------------------------------------------------
# Transport mode
# ---------------------------------------------------------------------------


def get_transport_mode() -> str:
    """Return the persisted transport mode.

    One of ``"local"``, ``"cloud"`` or ``"lan"``.  Defaults to ``"local"``
    when nothing has been saved yet (matches the wizard's default selection).
    """
    s = _s()
    value = str(s.value(_KEY_TRANSPORT_MODE, TRANSPORT_LOCAL))
    return value if value in _VALID_TRANSPORTS else TRANSPORT_LOCAL


def set_transport_mode(mode: str) -> None:
    """Persist the transport mode.  Raises ValueError on unknown mode."""
    if mode not in _VALID_TRANSPORTS:
        raise ValueError(
            f"transport mode must be one of {sorted(_VALID_TRANSPORTS)}; got {mode!r}"
        )
    s = _s()
    s.setValue(_KEY_TRANSPORT_MODE, mode)
    s.sync()


def get_prefer_grpc() -> bool:
    """Return True if the user prefers gRPC when both transports are available.

    Defaults to True — gRPC is materially faster than REST for list/watch
    operations and is the recommended transport on local + LAN deployments.
    Cloud deployments override this at call-site (gRPC isn't reachable
    through most cloud reverse proxies).
    """
    s = _s()
    raw = s.value(_KEY_PREFER_GRPC, True)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.lower() in ("1", "true", "yes", "on")
    return bool(raw)


def set_prefer_grpc(prefer: bool) -> None:
    s = _s()
    s.setValue(_KEY_PREFER_GRPC, bool(prefer))
    s.sync()


# ---------------------------------------------------------------------------
# Auth token
# ---------------------------------------------------------------------------


def get_auth_token() -> str:
    """Return the persisted bearer token, or '' if not set."""
    if env := os.environ.get("SAEBOOKS_API_TOKEN"):
        return env
    s = _s()
    return str(s.value(_KEY_TOKEN, ""))


def set_auth_token(token: str) -> None:
    """Persist the bearer token and keep api/token in sync."""
    s = _s()
    s.setValue(_KEY_TOKEN, token)
    s.setValue(_API_TOKEN_KEY, token)
    s.sync()


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------


def get_company_id() -> str:
    """Return the persisted company UUID, or '' if not set."""
    s = _s()
    return str(s.value(_KEY_COMPANY_ID, ""))


def set_company_id(company_id: str) -> None:
    s = _s()
    s.setValue(_KEY_COMPANY_ID, company_id)
    s.sync()


# ---------------------------------------------------------------------------
# First-run gate
# ---------------------------------------------------------------------------


def is_first_run() -> bool:
    """Return True when no server URL has been saved yet.

    The wizard sets ``saebooks/server/rest_url`` as its final step, so an
    empty value is the reliable signal that setup has not been completed.
    SAEBOOKS_API_URL env var bypasses the wizard (useful for dev/CI).
    """
    if os.environ.get("SAEBOOKS_API_URL"):
        return False
    return get_server_url() == ""
