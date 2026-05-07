"""First-run wizard — Page 5: Done."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWizardPage,
)


class DonePage(QWizardPage):
    """Final page — setup complete."""

    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.setTitle("You're all set!")
        self.setSubTitle("SAE Books is configured and ready to use.")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        body = QLabel(
            "Click Finish to start using SAE Books.\n\n"
            "You can change the server URL and sign-in details at any time\n"
            "from the application settings."
        )
        body.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        body.setWordWrap(True)
        layout.addWidget(body)
        layout.addStretch()
