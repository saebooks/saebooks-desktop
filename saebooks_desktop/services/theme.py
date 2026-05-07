"""Theme application helpers.

Reads the ``saebooks/ui/theme`` preference from QSettings and applies the
appropriate Qt style and palette to the running QApplication instance.

Supported themes:
  - "Dark"   — Fusion style + dark QPalette
  - "Light"  — Fusion style + default QPalette
  - "System" — leave OS default (no style/palette change)
"""
from __future__ import annotations


def _dark_palette():
    """Return a standard Qt dark QPalette."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPalette

    palette = QPalette()

    dark = QColor(45, 45, 45)
    mid_dark = QColor(66, 66, 66)
    light_text = QColor(220, 220, 220)
    disabled_text = QColor(128, 128, 128)
    highlight = QColor(42, 130, 218)
    highlight_text = QColor(255, 255, 255)
    link = QColor(42, 130, 218)
    base = QColor(25, 25, 25)
    alt_base = QColor(53, 53, 53)
    tool_tip_base = QColor(255, 255, 220)
    tool_tip_text = QColor(0, 0, 0)

    palette.setColor(QPalette.ColorRole.Window, dark)
    palette.setColor(QPalette.ColorRole.WindowText, light_text)
    palette.setColor(QPalette.ColorRole.Base, base)
    palette.setColor(QPalette.ColorRole.AlternateBase, alt_base)
    palette.setColor(QPalette.ColorRole.ToolTipBase, tool_tip_base)
    palette.setColor(QPalette.ColorRole.ToolTipText, tool_tip_text)
    palette.setColor(QPalette.ColorRole.Text, light_text)
    palette.setColor(QPalette.ColorRole.Button, mid_dark)
    palette.setColor(QPalette.ColorRole.ButtonText, light_text)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, link)
    palette.setColor(QPalette.ColorRole.Highlight, highlight)
    palette.setColor(QPalette.ColorRole.HighlightedText, highlight_text)

    # Disabled group
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_text)

    return palette


def apply_theme(theme: str) -> None:
    """Apply *theme* to the running QApplication instance.

    Args:
        theme: One of ``"Dark"``, ``"Light"``, or ``"System"``.
            Any unrecognised value is treated as ``"System"``.
    """
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return

    if theme == "Dark":
        app.setStyle("Fusion")
        app.setPalette(_dark_palette())
    elif theme == "Light":
        app.setStyle("Fusion")
        # Reset to default palette
        from PySide6.QtGui import QPalette
        app.setPalette(QPalette())
    # "System" — leave OS default, do nothing


def apply_theme_from_settings() -> None:
    """Read theme from QSettings and apply it.

    Reads ``saebooks/ui/theme`` (default ``"System"``) and calls
    :func:`apply_theme`.
    """
    from saebooks_desktop.views.preferences_dialog import get_theme

    apply_theme(get_theme())
