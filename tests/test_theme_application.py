"""Tests for theme application — dark palette, light palette, system pass-through.

All tests run offscreen.  QSettings is isolated by patching get_theme() so that
the real user settings store is never read or written.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---------------------------------------------------------------------------
# Session-scoped QApplication fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestApplyThemeDark:
    def test_dark_theme_sets_fusion_style(self, qapp) -> None:
        """apply_theme('Dark') must set Fusion style on the app."""
        from saebooks_desktop.services.theme import apply_theme

        apply_theme("Dark")
        assert qapp.style().objectName().lower() == "fusion"

    def test_dark_theme_darkens_window_role(self, qapp) -> None:
        """Dark palette Window colour must be darker than mid-grey (< 128 value)."""
        from saebooks_desktop.services.theme import apply_theme

        apply_theme("Dark")
        window_color = qapp.palette().color(qapp.palette().ColorRole.Window)
        # Any of R/G/B should be dark — check value (lightness)
        assert window_color.value() < 128, (
            f"Expected dark Window color, got value={window_color.value()}"
        )

    def test_dark_theme_light_window_text(self, qapp) -> None:
        """Dark palette WindowText colour must be light (value > 128)."""
        from saebooks_desktop.services.theme import apply_theme

        apply_theme("Dark")
        text_color = qapp.palette().color(qapp.palette().ColorRole.WindowText)
        assert text_color.value() > 128, (
            f"Expected light WindowText color, got value={text_color.value()}"
        )


class TestApplyThemeLight:
    def test_light_theme_sets_fusion_style(self, qapp) -> None:
        """apply_theme('Light') must set Fusion style on the app."""
        from saebooks_desktop.services.theme import apply_theme

        apply_theme("Light")
        assert qapp.style().objectName().lower() == "fusion"

    def test_light_theme_resets_palette(self, qapp) -> None:
        """After Light theme, the palette Window colour must be lighter than Dark."""
        from saebooks_desktop.services.theme import apply_theme

        # First go dark, then switch to light.
        apply_theme("Dark")
        dark_value = qapp.palette().color(qapp.palette().ColorRole.Window).value()

        apply_theme("Light")
        light_value = qapp.palette().color(qapp.palette().ColorRole.Window).value()

        assert light_value > dark_value, (
            f"Light palette Window ({light_value}) should be brighter than "
            f"dark palette Window ({dark_value})"
        )


class TestApplyThemeSystem:
    def test_system_theme_does_not_raise(self, qapp) -> None:
        """apply_theme('System') must not raise."""
        from saebooks_desktop.services.theme import apply_theme

        apply_theme("System")  # should be a no-op, not crash

    def test_unknown_theme_does_not_raise(self, qapp) -> None:
        """apply_theme with an unknown value must not raise."""
        from saebooks_desktop.services.theme import apply_theme

        apply_theme("UnknownTheme")  # treated as System/no-op


class TestApplyThemeFromSettings:
    def test_reads_and_applies_dark_from_settings(self, qapp) -> None:
        """apply_theme_from_settings must apply dark theme when preference is Dark."""
        from saebooks_desktop.services.theme import apply_theme_from_settings

        with patch(
            "saebooks_desktop.views.preferences_dialog.get_theme",
            return_value="Dark",
        ):
            apply_theme_from_settings()

        # Dark was applied — window color must be dark.
        window_color = qapp.palette().color(qapp.palette().ColorRole.Window)
        assert window_color.value() < 128

    def test_reads_and_applies_light_from_settings(self, qapp) -> None:
        """apply_theme_from_settings must apply light theme when preference is Light."""
        from saebooks_desktop.services.theme import apply_theme, apply_theme_from_settings

        # Ensure dark first so we can verify the change.
        apply_theme("Dark")

        with patch(
            "saebooks_desktop.views.preferences_dialog.get_theme",
            return_value="Light",
        ):
            apply_theme_from_settings()

        light_value = qapp.palette().color(qapp.palette().ColorRole.Window).value()
        assert light_value > 128


class TestPreferencesDialogThemeReapply:
    def test_preferences_ok_calls_apply_theme(self, qapp) -> None:
        """PreferencesDialog OK must call apply_theme with the selected theme."""
        from saebooks_desktop.views.preferences_dialog import PreferencesDialog

        dlg = PreferencesDialog()

        # Select "Dark" in the theme combo
        idx = dlg._theme_combo.findText("Dark")
        dlg._theme_combo.setCurrentIndex(idx)

        with patch(
            "saebooks_desktop.services.theme.apply_theme"
        ) as mock_apply:
            dlg._on_accept()

        mock_apply.assert_called_once_with("Dark")
