"""Tests for the first-run wizard WelcomePage."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestWelcomePage:
    def test_instantiates(self, qapp) -> None:
        from saebooks_desktop.wizard.pages.welcome import WelcomePage

        page = WelcomePage()
        assert page is not None

    def test_title_contains_brand_product_name(self, qapp) -> None:
        from saebooks_desktop.branding import get_brand
        from saebooks_desktop.wizard.pages.welcome import WelcomePage

        page = WelcomePage()
        assert get_brand().product_name in page.title()

    def test_title_follows_tasur_brand(self, qapp, monkeypatch) -> None:
        monkeypatch.setenv("SAEBOOKS_BRAND", "tasur")
        from saebooks_desktop.wizard.pages.welcome import WelcomePage

        page = WelcomePage()
        assert "tasur" in page.title()
        assert "SAE Books" not in page.title()

    def test_subtitle_contains_version(self, qapp) -> None:
        from saebooks_desktop.wizard.pages.welcome import WelcomePage

        page = WelcomePage()
        # Version string is in subtitle
        from saebooks_desktop import __version__

        assert __version__ in page.subTitle()

    def test_is_complete_always_true(self, qapp) -> None:
        """Welcome page has no required fields — always complete."""
        from saebooks_desktop.wizard.pages.welcome import WelcomePage

        page = WelcomePage()
        assert page.isComplete() is True
