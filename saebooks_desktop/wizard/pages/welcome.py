"""First-run wizard — Page 1: Welcome."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWizardPage,
)

from saebooks_desktop import __version__ as _VERSION  # type: ignore[attr-defined]
from saebooks_desktop.branding import get_brand


def _version_str() -> str:
    try:
        return str(_VERSION)
    except Exception:  # noqa: BLE001
        return "0.1"


class WelcomePage(QWizardPage):
    """Introductory page — branding and version."""

    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        brand = get_brand()
        self.setTitle(f"Welcome to {brand.product_name}")
        self.setSubTitle(
            f"Version {_version_str()}  —  {brand.tagline}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        body = QLabel(
            f"This wizard will help you connect to your {brand.product_name} "
            "server\nand sign in to your account.\n\n"
            "Click Next to get started."
        )
        body.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        body.setWordWrap(True)
        layout.addWidget(body)
        layout.addStretch()
