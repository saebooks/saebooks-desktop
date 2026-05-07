"""Tests for PreferencesDialog (views/preferences_dialog.py).

All tests run offscreen.  QSettings are isolated to a throw-away store.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    """Redirect preferences_dialog._s() to a throw-away QSettings store."""
    import saebooks_desktop.views.preferences_dialog as m

    def _test_settings():
        from PySide6.QtCore import QSettings
        return QSettings("_saebooks_test_", "_prefs_test_")

    monkeypatch.setattr(m, "_s", _test_settings)

    yield

    # Clean up the throw-away store
    from PySide6.QtCore import QSettings
    s = QSettings("_saebooks_test_", "_prefs_test_")
    s.clear()
    s.sync()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_dialog(qapp):
    from saebooks_desktop.views.preferences_dialog import PreferencesDialog
    return PreferencesDialog()


# ---------------------------------------------------------------------------
# Widget presence
# ---------------------------------------------------------------------------

class TestWidgetsPresent:
    def test_theme_combo_present(self, qapp) -> None:
        dlg = _make_dialog(qapp)
        assert dlg._theme_combo is not None

    def test_date_format_combo_present(self, qapp) -> None:
        dlg = _make_dialog(qapp)
        assert dlg._date_format_combo is not None

    def test_page_size_combo_present(self, qapp) -> None:
        dlg = _make_dialog(qapp)
        assert dlg._page_size_combo is not None

    def test_startup_combo_present(self, qapp) -> None:
        dlg = _make_dialog(qapp)
        assert dlg._startup_combo is not None

    def test_button_box_present(self, qapp) -> None:
        dlg = _make_dialog(qapp)
        assert dlg._button_box is not None


# ---------------------------------------------------------------------------
# Combo contents
# ---------------------------------------------------------------------------

class TestComboContents:
    def test_theme_options(self, qapp) -> None:
        dlg = _make_dialog(qapp)
        items = [dlg._theme_combo.itemText(i) for i in range(dlg._theme_combo.count())]
        assert items == ["Light", "Dark", "System"]

    def test_date_format_options(self, qapp) -> None:
        dlg = _make_dialog(qapp)
        items = [dlg._date_format_combo.itemText(i) for i in range(dlg._date_format_combo.count())]
        assert "DD/MM/YYYY" in items
        assert "YYYY-MM-DD" in items

    def test_page_size_options(self, qapp) -> None:
        dlg = _make_dialog(qapp)
        items = [dlg._page_size_combo.itemText(i) for i in range(dlg._page_size_combo.count())]
        assert "25" in items
        assert "50" in items
        assert "100" in items

    def test_startup_options(self, qapp) -> None:
        dlg = _make_dialog(qapp)
        items = [dlg._startup_combo.itemText(i) for i in range(dlg._startup_combo.count())]
        assert "Remember last view" in items
        assert "Always open to Dashboard" in items


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------

class TestDefaults:
    def test_default_theme_is_system(self, qapp) -> None:
        dlg = _make_dialog(qapp)
        assert dlg._theme_combo.currentText() == "System"

    def test_default_date_format_is_au(self, qapp) -> None:
        dlg = _make_dialog(qapp)
        assert dlg._date_format_combo.currentText() == "DD/MM/YYYY"

    def test_default_page_size_is_25(self, qapp) -> None:
        dlg = _make_dialog(qapp)
        assert dlg._page_size_combo.currentText() == "25"

    def test_default_startup_is_remember(self, qapp) -> None:
        dlg = _make_dialog(qapp)
        assert dlg._startup_combo.currentText() == "Remember last view"


# ---------------------------------------------------------------------------
# OK saves to QSettings
# ---------------------------------------------------------------------------

class TestOKSaves:
    def test_ok_saves_theme(self, qapp) -> None:
        import saebooks_desktop.views.preferences_dialog as m

        dlg = _make_dialog(qapp)
        dlg._theme_combo.setCurrentText("Dark")
        dlg._on_accept()
        assert m._s().value(m._KEY_THEME) == "Dark"

    def test_ok_saves_date_format(self, qapp) -> None:
        import saebooks_desktop.views.preferences_dialog as m

        dlg = _make_dialog(qapp)
        dlg._date_format_combo.setCurrentText("YYYY-MM-DD")
        dlg._on_accept()
        assert m._s().value(m._KEY_DATE_FORMAT) == "YYYY-MM-DD"

    def test_ok_saves_page_size(self, qapp) -> None:
        import saebooks_desktop.views.preferences_dialog as m

        dlg = _make_dialog(qapp)
        dlg._page_size_combo.setCurrentText("100")
        dlg._on_accept()
        assert m._s().value(m._KEY_PAGE_SIZE) == "100"

    def test_ok_saves_startup_view(self, qapp) -> None:
        import saebooks_desktop.views.preferences_dialog as m

        dlg = _make_dialog(qapp)
        dlg._startup_combo.setCurrentText("Always open to Dashboard")
        dlg._on_accept()
        assert m._s().value(m._KEY_STARTUP_VIEW) == "Always open to Dashboard"


# ---------------------------------------------------------------------------
# Cancel discards changes
# ---------------------------------------------------------------------------

class TestCancelDiscards:
    def test_cancel_does_not_save(self, qapp) -> None:
        import saebooks_desktop.views.preferences_dialog as m

        dlg = _make_dialog(qapp)
        # Set combo to something non-default
        dlg._theme_combo.setCurrentText("Light")
        # Reject (Cancel) — do NOT call _on_accept
        dlg.reject()
        # The store should still have the default (or whatever was there before)
        stored = m._s().value(m._KEY_THEME, "System")
        assert stored == "System"


# ---------------------------------------------------------------------------
# Round-trip persistence
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_round_trip_page_size(self, qapp) -> None:
        import saebooks_desktop.views.preferences_dialog as m

        dlg = _make_dialog(qapp)
        dlg._page_size_combo.setCurrentText("50")
        dlg._on_accept()

        # Create a second dialog — should pre-select the saved value
        dlg2 = _make_dialog(qapp)
        assert dlg2._page_size_combo.currentText() == "50"

    def test_round_trip_theme(self, qapp) -> None:
        import saebooks_desktop.views.preferences_dialog as m

        dlg = _make_dialog(qapp)
        dlg._theme_combo.setCurrentText("Dark")
        dlg._on_accept()

        dlg2 = _make_dialog(qapp)
        assert dlg2._theme_combo.currentText() == "Dark"
