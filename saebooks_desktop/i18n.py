"""Lightweight gettext-based UI translation (en / et / ru).

The compiled catalogs under ``saebooks_desktop/i18n_data/<locale>/
LC_MESSAGES/messages.mo`` are reused verbatim from saebooks-web, so any
UI string whose English text matches a web msgid translates for free.
Unknown strings fall through to English (gettext identity fallback).

Locale selection order: ``SAEBOOKS_LOCALE`` env var, then QSettings
``i18n/locale``, then the active brand's ``default_locale``.

Usage::

    from saebooks_desktop.i18n import tr
    label = QLabel(tr("Invoices"))

``tr()`` resolves the catalog lazily on first call and caches it;
``set_locale()`` persists a choice and resets the cache (existing
widgets keep their strings until rebuilt — PoC-acceptable).
"""
from __future__ import annotations

import gettext
import os
from pathlib import Path

_LOCALE_QSETTINGS_KEY = "i18n/locale"
_SUPPORTED = ("en", "et", "ru")

_catalog: gettext.NullTranslations | None = None
_active_locale: str | None = None


def _locale_dir() -> Path:
    return Path(__file__).parent / "i18n_data"


def get_locale() -> str:
    """Return the active locale code (env > QSettings > brand default)."""
    loc = os.environ.get("SAEBOOKS_LOCALE", "").strip().lower()
    if loc in _SUPPORTED:
        return loc
    try:
        from PySide6.QtCore import QSettings

        s = QSettings("SAE Engineering", "SAE Books")
        loc = str(s.value(_LOCALE_QSETTINGS_KEY, "") or "").strip().lower()
        if loc in _SUPPORTED:
            return loc
    except Exception:  # noqa: BLE001 — QSettings unavailable in bare tests
        pass
    from saebooks_desktop.branding import get_brand

    return get_brand().default_locale


def set_locale(locale: str) -> None:
    """Persist the locale to QSettings and reset the catalog cache."""
    if locale not in _SUPPORTED:
        raise ValueError(f"Unsupported locale: {locale!r}")
    from PySide6.QtCore import QSettings

    s = QSettings("SAE Engineering", "SAE Books")
    s.setValue(_LOCALE_QSETTINGS_KEY, locale)
    s.sync()
    reset_catalog()


def reset_catalog() -> None:
    """Drop the cached catalog so the next tr() re-resolves the locale."""
    global _catalog, _active_locale
    _catalog = None
    _active_locale = None


def tr(message: str) -> str:
    """Translate *message* for the active locale (English passthrough)."""
    global _catalog, _active_locale
    loc = get_locale()
    if _catalog is None or _active_locale != loc:
        if loc == "en":
            _catalog = gettext.NullTranslations()
        else:
            _catalog = gettext.translation(
                "messages",
                localedir=str(_locale_dir()),
                languages=[loc],
                fallback=True,
            )
        _active_locale = loc
    return _catalog.gettext(message)
