"""Application icon — multi-resolution, brand-aware.

Every user-visible surface (window titlebar, taskbar/dock, Alt-Tab) must
show the brand icon, never the generic Qt/framework one.  The pixel
sources are pre-rendered PNGs in ``assets/icons/<stem>-<size>.png``
(generated from the brand SVGs at 16–256 px); the SVG itself is the
last-resort fallback.

Frozen (cx_Freeze/MSI) builds ship the package inside a zip, where
``Path(__file__)`` does not resolve to a real directory — for those,
``deploy/windows/setup_freeze.py`` copies the icons to ``assets/icons``
beside the executable and we look there first.
"""
from __future__ import annotations

import sys
from pathlib import Path

ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _candidate_icon_dirs() -> list[Path]:
    dirs: list[Path] = []
    if getattr(sys, "frozen", False):
        # cx_Freeze layout: icons beside the executable (see setup_freeze.py).
        dirs.append(Path(sys.executable).parent / "assets" / "icons")
    dirs.append(Path(__file__).resolve().parent / "assets" / "icons")
    return dirs


def brand_icon():
    """Return a multi-resolution ``QIcon`` for the active brand.

    May return a null icon only if every asset lookup fails (broken
    install); callers should skip ``setWindowIcon`` in that case rather
    than set an empty icon.
    """
    from PySide6.QtGui import QIcon

    from saebooks_desktop.branding import get_brand

    brand = get_brand()
    stem = Path(brand.logo_filename).stem

    icon = QIcon()
    for icons_dir in _candidate_icon_dirs():
        for size in ICON_SIZES:
            p = icons_dir / f"{stem}-{size}.png"
            if p.is_file():
                icon.addFile(str(p))
        if not icon.isNull():
            return icon

    # Fallback: load the SVG directly (needs the Qt SVG image plugin).
    svg = Path(__file__).resolve().parent / "assets" / brand.logo_filename
    if svg.is_file():
        return QIcon(str(svg))
    return icon


def apply_app_icon(app) -> None:
    """Set the brand icon application-wide and fix Windows taskbar identity.

    Must run after ``QApplication`` exists and before any window is shown.
    """
    if sys.platform == "win32":
        # Give the process an explicit AppUserModelID so the Windows
        # taskbar shows OUR icon (not the Python/host one) and groups the
        # app's windows under it.  Matches the com.saebooks.* namespace
        # used by the macOS bundles.
        try:
            import ctypes

            from saebooks_desktop.branding import get_brand

            appid = f"com.saebooks.desktop.{get_brand().id}"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
        except Exception:  # noqa: BLE001 — cosmetic; never block startup
            pass

    icon = brand_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
