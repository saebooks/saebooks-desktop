"""User Preferences dialog — local/UI settings stored in QSettings.

Settings managed:
    saebooks/ui/theme         — Light / Dark / System
    saebooks/ui/date_format   — DD/MM/YYYY  / YYYY-MM-DD
    saebooks/ui/page_size     — 25 / 50 / 100 (rows per page in list views)
    saebooks/ui/startup_view  — Remember last view / Always open to Dashboard

Note: Theme switching does not apply immediately in this cycle (E/9). The
preference is stored and will be applied in E/10.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QVBoxLayout,
    QWidget,
)

_ORG = "SAE Engineering"
_APP = "SAE Books"

_KEY_THEME = "saebooks/ui/theme"
_KEY_DATE_FORMAT = "saebooks/ui/date_format"
_KEY_PAGE_SIZE = "saebooks/ui/page_size"
_KEY_STARTUP_VIEW = "saebooks/ui/startup_view"

_THEMES = ["Light", "Dark", "System"]
_DATE_FORMATS = ["DD/MM/YYYY", "YYYY-MM-DD"]
_PAGE_SIZES = ["25", "50", "100"]
_STARTUP_OPTIONS = ["Remember last view", "Always open to Dashboard"]

_DEFAULTS = {
    _KEY_THEME: "System",
    _KEY_DATE_FORMAT: "DD/MM/YYYY",
    _KEY_PAGE_SIZE: "25",
    _KEY_STARTUP_VIEW: "Remember last view",
}


def _s() -> QSettings:
    return QSettings(_ORG, _APP)


def get_theme() -> str:
    return str(_s().value(_KEY_THEME, _DEFAULTS[_KEY_THEME]))


def get_date_format() -> str:
    return str(_s().value(_KEY_DATE_FORMAT, _DEFAULTS[_KEY_DATE_FORMAT]))


def get_page_size() -> int:
    return int(_s().value(_KEY_PAGE_SIZE, _DEFAULTS[_KEY_PAGE_SIZE]))


def get_startup_view() -> str:
    return str(_s().value(_KEY_STARTUP_VIEW, _DEFAULTS[_KEY_STARTUP_VIEW]))


class PreferencesDialog(QDialog):
    """User preferences dialog — local UI settings.

    Shows combos for theme, date format, page size, and startup behaviour.
    OK saves to QSettings; Cancel discards changes.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(360)

        s = _s()

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setContentsMargins(12, 12, 12, 12)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        # Theme
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(_THEMES)
        current_theme = str(s.value(_KEY_THEME, _DEFAULTS[_KEY_THEME]))
        idx = self._theme_combo.findText(current_theme)
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)
        form.addRow("Theme:", self._theme_combo)

        # Date format
        self._date_format_combo = QComboBox()
        self._date_format_combo.addItems(_DATE_FORMATS)
        current_fmt = str(s.value(_KEY_DATE_FORMAT, _DEFAULTS[_KEY_DATE_FORMAT]))
        idx = self._date_format_combo.findText(current_fmt)
        if idx >= 0:
            self._date_format_combo.setCurrentIndex(idx)
        form.addRow("Date format:", self._date_format_combo)

        # Page size
        self._page_size_combo = QComboBox()
        self._page_size_combo.addItems(_PAGE_SIZES)
        current_ps = str(s.value(_KEY_PAGE_SIZE, _DEFAULTS[_KEY_PAGE_SIZE]))
        idx = self._page_size_combo.findText(current_ps)
        if idx >= 0:
            self._page_size_combo.setCurrentIndex(idx)
        form.addRow("Default page size:", self._page_size_combo)

        # Startup behaviour
        self._startup_combo = QComboBox()
        self._startup_combo.addItems(_STARTUP_OPTIONS)
        current_sv = str(s.value(_KEY_STARTUP_VIEW, _DEFAULTS[_KEY_STARTUP_VIEW]))
        idx = self._startup_combo.findText(current_sv)
        if idx >= 0:
            self._startup_combo.setCurrentIndex(idx)
        form.addRow("Startup behaviour:", self._startup_combo)

        # Dialog buttons
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self._button_box.accepted.connect(self._on_accept)
        self._button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(form_widget)
        layout.addWidget(self._button_box)

    def _on_accept(self) -> None:
        s = _s()
        s.setValue(_KEY_THEME, self._theme_combo.currentText())
        s.setValue(_KEY_DATE_FORMAT, self._date_format_combo.currentText())
        s.setValue(_KEY_PAGE_SIZE, self._page_size_combo.currentText())
        s.setValue(_KEY_STARTUP_VIEW, self._startup_combo.currentText())
        s.sync()
        # Re-apply theme immediately so the user sees the change without restart.
        from saebooks_desktop.services.theme import apply_theme
        apply_theme(self._theme_combo.currentText())
        self.accept()
