"""First-run wizard — Page 1: Welcome."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWizardPage,
)

from saebooks_desktop import __version__ as _VERSION  # type: ignore[attr-defined]


def _version_str() -> str:
    try:
        return str(_VERSION)
    except Exception:  # noqa: BLE001
        return "0.1"


class WelcomePage(QWizardPage):
    """Introductory page — branding and version."""

    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.setTitle("Welcome to SAE Books")
        self.setSubTitle(
            f"Version {_version_str()}  —  self-hosted AU-compliant accounting"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        body = QLabel(
            "This wizard will help you connect to your SAE Books server\n"
            "and sign in to your account.\n\n"
            "Click Next to get started."
        )
        body.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        body.setWordWrap(True)
        layout.addWidget(body)
        layout.addStretch()
