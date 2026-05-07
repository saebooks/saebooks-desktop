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

    def test_title_contains_sae_books(self, qapp) -> None:
        from saebooks_desktop.wizard.pages.welcome import WelcomePage

        page = WelcomePage()
        assert "SAE Books" in page.title()

    def test_subtitle_contains_version(self, qapp) -> None:
        from saebooks_desktop.wizard.pages.welcome import WelcomePage

        page = WelcomePage()
        # Version string is in subtitle
        assert "0.1" in page.subTitle()

    def test_is_complete_always_true(self, qapp) -> None:
        """Welcome page has no required fields — always complete."""
        from saebooks_desktop.wizard.pages.welcome import WelcomePage

        page = WelcomePage()
        assert page.isComplete() is True
