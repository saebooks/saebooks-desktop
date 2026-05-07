"""QSettings wrapper — persists server URL and API token across sessions."""
from __future__ import annotations

import os

from PySide6.QtCore import QSettings

_ORG = "SAE Engineering"
_APP = "SAE Books"


def _settings() -> QSettings:
    return QSettings(_ORG, _APP)


def get_api_url() -> str:
    """Return the configured API base URL, env var overrides stored value."""
    if env := os.environ.get("SAEBOOKS_API_URL"):
        return env.rstrip("/")
    s = _settings()
    return str(s.value("api/url", "http://localhost:8042")).rstrip("/")


def set_api_url(url: str) -> None:
    s = _settings()
    s.setValue("api/url", url.rstrip("/"))
    s.sync()


def get_api_token() -> str:
    """Return the configured bearer token, env var overrides stored value."""
    if env := os.environ.get("SAEBOOKS_API_TOKEN"):
        return env
    s = _settings()
    return str(s.value("api/token", ""))


def set_api_token(token: str) -> None:
    s = _settings()
    s.setValue("api/token", token)
    s.sync()
