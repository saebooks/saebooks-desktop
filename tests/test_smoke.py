"""Smoke tests — offscreen Qt instantiation.

These tests verify that:
1. QApplication + MainWindow can be created without crashing.
2. ContactsView instantiates correctly even when the API is unavailable
   (graceful fallback: offline banner shown, table stays empty, no crash).

All tests run offscreen — no display server required.
"""
from __future__ import annotations

import os

# Force offscreen platform BEFORE any Qt import so it takes effect.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


import pytest


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication — only one may exist per process."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestMainWindowSmoke:
    def test_main_window_instantiates(self, qapp) -> None:
        """MainWindow must construct without raising."""
        from saebooks_desktop.main_window import MainWindow

        window = MainWindow()
        assert window is not None
        assert window.windowTitle() == "SAE Books"

    def test_main_window_minimum_size(self, qapp) -> None:
        """MainWindow must enforce minimum size 1024×768."""
        from saebooks_desktop.main_window import MainWindow

        window = MainWindow()
        assert window.minimumWidth() == 1024
        assert window.minimumHeight() == 768

    def test_main_window_has_status_bar(self, qapp) -> None:
        """MainWindow must have a status bar."""
        from saebooks_desktop.main_window import MainWindow

        window = MainWindow()
        assert window.statusBar() is not None

    def test_main_window_nav_has_contacts(self, qapp) -> None:
        """Sidebar must include a 'Contacts' item."""
        from saebooks_desktop.main_window import MainWindow

        window = MainWindow()
        nav_labels = [
            window._nav.item(i).text()
            for i in range(window._nav.count())
        ]
        assert "Contacts" in nav_labels

    def test_main_window_nav_contacts_enabled(self, qapp) -> None:
        """Contacts nav item must be enabled (selectable)."""
        from PySide6.QtCore import Qt
        from saebooks_desktop.main_window import MainWindow

        window = MainWindow()
        for i in range(window._nav.count()):
            item = window._nav.item(i)
            if item.text() == "Contacts":
                assert item.flags() & Qt.ItemFlag.ItemIsEnabled
                break

    def test_greyed_out_nav_items(self, qapp) -> None:
        """Dashboard must be disabled.

        Sales, Purchases, Accounts, Journal Entries, Banking, and Payments
        are now live views and must be enabled.
        """
        from PySide6.QtCore import Qt
        from saebooks_desktop.main_window import MainWindow

        window = MainWindow()
        disabled_labels = {"Dashboard"}
        for i in range(window._nav.count()):
            item = window._nav.item(i)
            if item.text() in disabled_labels:
                assert not (item.flags() & Qt.ItemFlag.ItemIsEnabled), (
                    f"{item.text()} should be disabled"
                )

    def test_sales_and_purchases_nav_enabled(self, qapp) -> None:
        """Sales and Purchases nav items must be enabled (live views wired in)."""
        from PySide6.QtCore import Qt
        from saebooks_desktop.main_window import MainWindow

        window = MainWindow()
        live_labels = {"Sales", "Purchases"}
        found: set[str] = set()
        for i in range(window._nav.count()):
            item = window._nav.item(i)
            if item.text() in live_labels:
                found.add(item.text())
                assert item.flags() & Qt.ItemFlag.ItemIsEnabled, (
                    f"{item.text()} should be enabled"
                )
        assert found == live_labels, f"Nav items not found: {live_labels - found}"

    def test_accounts_and_journal_entries_nav_enabled(self, qapp) -> None:
        """Accounts and Journal Entries nav items must be enabled (live views wired in)."""
        from PySide6.QtCore import Qt
        from saebooks_desktop.main_window import MainWindow

        window = MainWindow()
        live_labels = {"Accounts", "Journal Entries"}
        found: set[str] = set()
        for i in range(window._nav.count()):
            item = window._nav.item(i)
            if item.text() in live_labels:
                found.add(item.text())
                assert item.flags() & Qt.ItemFlag.ItemIsEnabled, (
                    f"{item.text()} should be enabled"
                )
        assert found == live_labels, f"Nav items not found: {live_labels - found}"

    def test_banking_and_payments_nav_enabled(self, qapp) -> None:
        """Banking and Payments nav items must be enabled (live views wired in)."""
        from PySide6.QtCore import Qt
        from saebooks_desktop.main_window import MainWindow

        window = MainWindow()
        live_labels = {"Banking", "Payments"}
        found: set[str] = set()
        for i in range(window._nav.count()):
            item = window._nav.item(i)
            if item.text() in live_labels:
                found.add(item.text())
                assert item.flags() & Qt.ItemFlag.ItemIsEnabled, (
                    f"{item.text()} should be enabled"
                )
        assert found == live_labels, f"Nav items not found: {live_labels - found}"

    def test_reports_nav_enabled(self, qapp) -> None:
        """Reports nav item must be enabled (ReportsView wired in)."""
        from PySide6.QtCore import Qt
        from saebooks_desktop.main_window import MainWindow

        window = MainWindow()
        for i in range(window._nav.count()):
            item = window._nav.item(i)
            if item.text() == "Reports":
                assert item.flags() & Qt.ItemFlag.ItemIsEnabled, "Reports should be enabled"
                return
        pytest.fail("Reports nav item not found")

    def test_settings_nav_enabled(self, qapp) -> None:
        """Settings nav item must be enabled (SettingsView wired in)."""
        from PySide6.QtCore import Qt
        from saebooks_desktop.main_window import MainWindow

        window = MainWindow()
        for i in range(window._nav.count()):
            item = window._nav.item(i)
            if item.text() == "Settings":
                assert item.flags() & Qt.ItemFlag.ItemIsEnabled, "Settings should be enabled"
                return
        pytest.fail("Settings nav item not found")

    def test_items_nav_enabled(self, qapp) -> None:
        """Items nav item must be enabled (ItemsView wired in)."""
        from PySide6.QtCore import Qt
        from saebooks_desktop.main_window import MainWindow

        window = MainWindow()
        for i in range(window._nav.count()):
            item = window._nav.item(i)
            if item.text() == "Items":
                assert item.flags() & Qt.ItemFlag.ItemIsEnabled, "Items should be enabled"
                return
        pytest.fail("Items nav item not found")

    def test_edit_menu_has_preferences(self, qapp) -> None:
        """Edit menu must contain a Preferences action."""
        from saebooks_desktop.main_window import MainWindow

        window = MainWindow()
        menu_bar = window.menuBar()
        edit_menu = None
        for action in menu_bar.actions():
            if "edit" in action.text().lower():
                edit_menu = action.menu()
                break
        assert edit_menu is not None, "Edit menu not found"
        action_texts = [a.text() for a in edit_menu.actions()]
        assert any("preferences" in t.lower() for t in action_texts)


class TestContactsViewSmoke:
    def test_contacts_view_instantiates_offline(self, qapp) -> None:
        """ContactsView must create without crash when API is unreachable."""
        from saebooks_desktop.views.contacts import ContactsView

        # API will be unreachable in test env — graceful fallback expected.
        view = ContactsView()
        assert view is not None

    def test_contacts_view_offline_banner_visible_when_unreachable(self, qapp) -> None:
        """Offline banner must be visible when the server is not reachable.

        Note: isVisible() returns False for widgets whose parent hasn't been
        shown yet (offscreen test). isHidden() reflects what setVisible() set,
        so 'not isHidden()' is the correct test for "banner was made visible".
        """
        from saebooks_desktop.views.contacts import ContactsView

        view = ContactsView()
        # In test env the server is not running — offline label should not be hidden.
        assert not view._offline_label.isHidden()

    def test_contacts_view_table_empty_when_offline(self, qapp) -> None:
        """Table must be empty (not crash) when the API is unavailable."""
        from saebooks_desktop.views.contacts import ContactsView

        view = ContactsView()
        # Table model should exist with 0 rows — not an exception.
        assert view._model.rowCount() == 0

    def test_contacts_view_has_refresh_and_new_buttons(self, qapp) -> None:
        """ContactsView must expose Refresh and New Contact buttons."""
        from saebooks_desktop.views.contacts import ContactsView

        view = ContactsView()
        assert view._refresh_btn is not None
        assert view._new_btn is not None


class TestSettingsSmoke:
    def test_get_api_url_default(self, monkeypatch) -> None:
        """Default API URL must be localhost:8042 when no env/settings present."""
        monkeypatch.delenv("SAEBOOKS_API_URL", raising=False)

        # Use a throw-away QSettings org/app name to avoid polluting real config.
        import saebooks_desktop.settings as settings_module

        original_settings = settings_module._settings

        def _mock_settings():
            from PySide6.QtCore import QSettings
            return QSettings("_saebooks_test_", "_saebooks_test_")

        settings_module._settings = _mock_settings
        try:
            url = settings_module.get_api_url()
            assert url == "http://localhost:8042"
        finally:
            settings_module._settings = original_settings

    def test_get_api_url_env_override(self, monkeypatch) -> None:
        """SAEBOOKS_API_URL env var must take priority over QSettings."""
        monkeypatch.setenv("SAEBOOKS_API_URL", "http://myserver:9000")
        import saebooks_desktop.settings as settings_module

        url = settings_module.get_api_url()
        assert url == "http://myserver:9000"


class TestAPIClientSmoke:
    def test_api_client_instantiates(self, monkeypatch) -> None:
        """APIClient must construct with default settings."""
        monkeypatch.setenv("SAEBOOKS_API_URL", "http://localhost:8042")
        monkeypatch.setenv("SAEBOOKS_API_TOKEN", "test-token")
        from saebooks_desktop.services.api_client import APIClient

        client = APIClient()
        assert client is not None

    def test_api_client_unreachable_returns_false(self, monkeypatch) -> None:
        """is_reachable() must return False when server is not up."""
        monkeypatch.setenv("SAEBOOKS_API_URL", "http://127.0.0.1:19999")
        monkeypatch.setenv("SAEBOOKS_API_TOKEN", "test-token")
        from saebooks_desktop.services.api_client import APIClient

        client = APIClient()
        assert client.is_reachable() is False


class TestLicenceSmoke:
    def test_load_licence_returns_community_without_jwt(self, tmp_path) -> None:
        """load_licence() must return Community tier when no JWT on disk."""
        from saebooks_desktop.licence import load_licence

        info = load_licence()
        assert info.tier == "community"
        assert info.valid is True
