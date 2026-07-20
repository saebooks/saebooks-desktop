"""Community-edition defaults — no licence chrome, no upsell.

The community build is the product, not a demo tier: when the licence
loader returns the community stub (the only thing it can return without
a real verified licence), the status bar must show NO licence badge.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_window(qapp):
    from saebooks_desktop.main_window import MainWindow

    mock_transport = MagicMock()
    mock_transport.is_reachable.return_value = False

    with (
        patch("saebooks_desktop.views.invoices.list_invoices", return_value=[]),
        patch("saebooks_desktop.views.bills.list_bills", return_value=[]),
        patch(
            "saebooks_desktop.services.api_client.APIClient.resolve_transport",
            return_value=mock_transport,
        ),
        patch(
            "saebooks_desktop.cache.sync.SyncEngine.isRunning",
            return_value=False,
        ),
    ):
        window = MainWindow()
    return window


class TestCommunityLicenceChrome:
    def test_community_stub_shows_no_licence_badge(self, qapp) -> None:
        window = _make_window(qapp)
        try:
            assert window._licence.tier == "community"
            assert window._tier_label.isHidden()
            # The label must not be parented into the status bar either.
            assert window._tier_label.parent() is not window.statusBar()
        finally:
            window.close()
            window.deleteLater()

    def test_licence_loader_never_raises(self) -> None:
        from saebooks_desktop.licence import load_licence

        info = load_licence()
        assert info.tier == "community"
