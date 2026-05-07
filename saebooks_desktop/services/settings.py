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
_KEY_TOKEN = "saebooks/auth/token"
_KEY_COMPANY_ID = "saebooks/auth/company_id"

# Mirror keys used by APIClient (saebooks_desktop.settings)
_API_URL_KEY = "api/url"
_API_TOKEN_KEY = "api/token"


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
