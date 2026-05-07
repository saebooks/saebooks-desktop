"""Tests for the first-run wizard DonePage."""
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


class TestDonePage:
    def test_instantiates(self, qapp) -> None:
        from saebooks_desktop.wizard.pages.done import DonePage

        page = DonePage()
        assert page is not None

    def test_title_indicates_completion(self, qapp) -> None:
        from saebooks_desktop.wizard.pages.done import DonePage

        page = DonePage()
        # Title should indicate success / readiness
        title_lower = page.title().lower()
        assert any(word in title_lower for word in ("set", "done", "ready", "complete", "finish"))
