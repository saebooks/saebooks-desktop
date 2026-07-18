"""Brand registry — SAE Books vs the tasur (Estonia) variant.

One binary, two skins. The brand decides product naming, the default
locale, the default currency shown before a company is loaded, and the
word used for consumption tax in UI chrome ("GST" vs "käibemaks").
Selection order: ``SAEBOOKS_BRAND`` env var, then QSettings
``brand/id``, then the built-in default (``saebooks``).

Company-derived values (base_currency, jurisdiction) always win over
brand defaults once a company is loaded — the brand only covers chrome
shown before/outside a company context.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

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


BRANDS: dict[str, Brand] = {
    "saebooks": Brand(
        id="saebooks",
        product_name="SAE Books",
        org_name="SAE Engineering",
        default_locale="en",
        default_currency="AUD",
        tax_label="GST",
        logo_filename="saebooks-desktop.svg",
    ),
    "tasur": Brand(
        id="tasur",
        product_name="tasur",
        org_name="tasur",
        default_locale="et",
        default_currency="EUR",
        tax_label="käibemaks",
        logo_filename="tasur.svg",
    ),
}

_DEFAULT_BRAND_ID = "saebooks"


def get_brand() -> Brand:
    """Return the active Brand (env > QSettings > default)."""
    brand_id = os.environ.get("SAEBOOKS_BRAND", "").strip().lower()
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
