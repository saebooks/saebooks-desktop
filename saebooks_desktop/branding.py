"""Brand registry — SAE Books vs the tasur (Estonia) variant.

One binary, two skins. The brand decides product naming, the default
locale, the default currency shown before a company is loaded, and the
word used for consumption tax in UI chrome ("GST" vs "käibemaks").
Selection order: ``SAEBOOKS_BRAND`` env var, then the brand baked into
a packaged artifact (``brand.cfg`` beside a frozen executable — the MSI
path; the AppImage bakes an env export into its entrypoint instead),
then QSettings ``brand/id``, then the built-in default (``saebooks``).
A branded artifact therefore stays its brand regardless of what another
build on the same machine persisted to QSettings.

Company-derived values (base_currency, jurisdiction) always win over
brand defaults once a company is loaded — the brand only covers chrome
shown before/outside a company context.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

_BRAND_QSETTINGS_KEY = "brand/id"


@dataclass(frozen=True)
class Brand:
    """Static branding facts for one product skin."""

    id: str
    product_name: str
    org_name: str
    default_locale: str
    default_currency: str
    tax_label: str
    logo_filename: str
    tagline: str = "self-hosted accounting"


BRANDS: dict[str, Brand] = {
    "saebooks": Brand(
        id="saebooks",
        product_name="SAE Books",
        org_name="SAE Engineering",
        default_locale="en",
        default_currency="AUD",
        tax_label="GST",
        logo_filename="saebooks-desktop.svg",
        tagline="self-hosted accounting",
    ),
    # tasur visual identity — Direction A "Selge" (2026-07-21). Brand anchor
    # navy #194291. Assets: tasur.svg (icon: #194291 tile, white "t",
    # #A9C2F5 dot) plus tasur-wordmark-on-{light,dark}.svg in assets/.
    # WCAG rules for any tasur-specific chrome: on LIGHT backgrounds use
    # #194291 (secondary #3563C7) for text/accents; on DARK backgrounds
    # never use #194291 as text — use #7D9EE8 or #A9C2F5 (wordmark ink
    # #DCE6FB); #194291 on dark only as a surface/tile with white content.
    "tasur": Brand(
        id="tasur",
        product_name="tasur",
        org_name="tasur",
        default_locale="et",
        default_currency="EUR",
        tax_label="käibemaks",
        logo_filename="tasur.svg",
        tagline="self-hosted accounting",
    ),
}

_DEFAULT_BRAND_ID = "saebooks"


def _baked_brand_id() -> str:
    """Return the brand baked into a packaged artifact, or ''.

    cx_Freeze (MSI) builds drop a one-line ``brand.cfg`` next to the frozen
    executable; the AppImage instead exports ``SAEBOOKS_BRAND`` from its
    entrypoint, so it never reaches this fallback.
    """
    if not getattr(sys, "frozen", False):
        return ""
    try:
        cfg = Path(sys.executable).parent / "brand.cfg"
        if cfg.exists():
            return cfg.read_text(encoding="utf-8").strip().lower()
    except OSError:
        pass
    return ""


def get_brand() -> Brand:
    """Return the active Brand (env > baked artifact > QSettings > default)."""
    brand_id = os.environ.get("SAEBOOKS_BRAND", "").strip().lower()
    if not brand_id:
        brand_id = _baked_brand_id()
    if not brand_id:
        try:
            from PySide6.QtCore import QSettings

            s = QSettings("SAE Engineering", "SAE Books")
            brand_id = str(s.value(_BRAND_QSETTINGS_KEY, "") or "").strip().lower()
        except Exception:  # noqa: BLE001 — QSettings unavailable in bare tests
            brand_id = ""
    return BRANDS.get(brand_id, BRANDS[_DEFAULT_BRAND_ID])


def set_brand(brand_id: str) -> None:
    """Persist the brand selection to QSettings (takes effect next launch)."""
    if brand_id not in BRANDS:
        raise ValueError(f"Unknown brand: {brand_id!r}")
    from PySide6.QtCore import QSettings

    s = QSettings("SAE Engineering", "SAE Books")
    s.setValue(_BRAND_QSETTINGS_KEY, brand_id)
    s.sync()
