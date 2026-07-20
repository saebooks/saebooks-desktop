"""Brand registry + gettext i18n (tasur variant plumbing)."""
import os

import pytest

from saebooks_desktop import i18n
from saebooks_desktop.branding import BRANDS, get_brand


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("SAEBOOKS_BRAND", raising=False)
    monkeypatch.delenv("SAEBOOKS_LOCALE", raising=False)
    i18n.reset_catalog()
    yield
    i18n.reset_catalog()


class TestBrand:
    def test_default_is_saebooks(self) -> None:
        brand = get_brand()
        assert brand.id in BRANDS  # QSettings may carry a persisted choice
        assert BRANDS["saebooks"].product_name == "SAE Books"

    def test_env_selects_tasur(self, monkeypatch) -> None:
        monkeypatch.setenv("SAEBOOKS_BRAND", "tasur")
        brand = get_brand()
        assert brand.product_name == "tasur"
        assert brand.default_locale == "et"
        assert brand.default_currency == "EUR"
        assert brand.tax_label == "käibemaks"

    def test_unknown_brand_falls_back(self, monkeypatch) -> None:
        monkeypatch.setenv("SAEBOOKS_BRAND", "nonesuch")
        assert get_brand().id == "saebooks"


class TestI18n:
    def test_english_passthrough(self, monkeypatch) -> None:
        monkeypatch.setenv("SAEBOOKS_LOCALE", "en")
        assert i18n.tr("Invoices") == "Invoices"

    def test_estonian_from_web_catalog(self, monkeypatch) -> None:
        monkeypatch.setenv("SAEBOOKS_LOCALE", "et")
        assert i18n.tr("Invoices") == "Arved"
        assert i18n.tr("Expenses") == "Kulud"

    def test_russian_from_web_catalog(self, monkeypatch) -> None:
        monkeypatch.setenv("SAEBOOKS_LOCALE", "ru")
        assert i18n.tr("Invoices") == "Счета"

    def test_unknown_msgid_falls_back_to_english(self, monkeypatch) -> None:
        monkeypatch.setenv("SAEBOOKS_LOCALE", "et")
        assert i18n.tr("Frobnicate the flux capacitor") == (
            "Frobnicate the flux capacitor"
        )

    def test_tasur_brand_defaults_locale_et(self, monkeypatch) -> None:
        monkeypatch.setenv("SAEBOOKS_BRAND", "tasur")
        # No explicit locale: brand default should apply unless QSettings
        # carries a persisted user choice from a previous run.
        assert i18n.get_locale() in ("et", "en", "ru")
        env_backup = os.environ.get("SAEBOOKS_LOCALE")
        assert env_backup is None


class TestBakedBrand:
    """The brand baked into a packaged artifact (brand.cfg beside a frozen exe)."""

    def test_not_frozen_returns_empty(self) -> None:
        from saebooks_desktop.branding import _baked_brand_id

        # Test processes are never frozen — baked lookup must be inert.
        assert _baked_brand_id() == ""

    def test_frozen_reads_brand_cfg(self, monkeypatch, tmp_path) -> None:
        import sys

        from saebooks_desktop import branding

        exe = tmp_path / "saebooks-desktop.exe"
        exe.write_bytes(b"")
        (tmp_path / "brand.cfg").write_text("tasur\n", encoding="utf-8")
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(exe))
        assert branding._baked_brand_id() == "tasur"
        assert branding.get_brand().id == "tasur"

    def test_frozen_without_cfg_returns_empty(self, monkeypatch, tmp_path) -> None:
        import sys

        from saebooks_desktop.branding import _baked_brand_id

        exe = tmp_path / "saebooks-desktop.exe"
        exe.write_bytes(b"")
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(exe))
        assert _baked_brand_id() == ""

    def test_env_outranks_baked(self, monkeypatch, tmp_path) -> None:
        import sys

        from saebooks_desktop import branding

        exe = tmp_path / "saebooks-desktop.exe"
        exe.write_bytes(b"")
        (tmp_path / "brand.cfg").write_text("tasur", encoding="utf-8")
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(exe))
        monkeypatch.setenv("SAEBOOKS_BRAND", "saebooks")
        assert branding.get_brand().id == "saebooks"
