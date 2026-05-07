"""First-run wizard — Page 3: Sign in.

Posts credentials to ``POST /api/v1/auth/login`` and stores the returned
bearer token in QSettings via ``services.settings.set_auth_token``.

If the endpoint does not exist yet (API gap), the test suite mocks it.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWizardPage,
)


class SignInPage(QWizardPage):
    """Wizard page for email + password authentication."""

    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.setTitle("Sign in")
        self.setSubTitle("Enter your SAE Books account credentials.")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        self._email_input = QLineEdit()
        self._email_input.setPlaceholderText("you@example.com")
        form.addRow("Email:", self._email_input)

        self._password_input = QLineEdit()
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_input.setPlaceholderText("••••••••")
        form.addRow("Password:", self._password_input)

        layout.addLayout(form)

        self._sign_in_btn = QPushButton("Sign In")
        self._sign_in_btn.clicked.connect(self._on_sign_in_clicked)
        layout.addWidget(self._sign_in_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        layout.addStretch()

        self._login_ok = False

    # ------------------------------------------------------------------
    # QWizardPage protocol
    # ------------------------------------------------------------------

    def isComplete(self) -> bool:
        return self._login_ok

    def initializePage(self) -> None:
        """Reset the page each time it is shown (wizard Back then Next)."""
        self._login_ok = False
        self._status_label.setText("")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_sign_in_clicked(self) -> None:
        email = self._email_input.text().strip()
        password = self._password_input.text()

        if not email:
            self._set_status(False, "Email is required.")
            return
        if not password:
            self._set_status(False, "Password is required.")
            return

        self._sign_in_btn.setEnabled(False)
        self._set_status(None, "Signing in…")

        from saebooks_desktop.services.auth import login
        from saebooks_desktop.services.settings import get_server_url

        base_url = get_server_url() or "http://localhost:8042"

        import httpx

        from saebooks_desktop.services.api_client import APIClient

        client = APIClient(base_url=base_url)

        try:
            token = login(client, email, password)
        except Exception as exc:  # noqa: BLE001
            self._set_status(False, str(exc))
            self._sign_in_btn.setEnabled(True)
            return

        from saebooks_desktop.services.settings import set_auth_token

        set_auth_token(token)
        self._login_ok = True
        self._set_status(True, "Signed in successfully.")
        self._sign_in_btn.setEnabled(True)
        self.completeChanged.emit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, ok: bool | None, message: str) -> None:
        if ok is True:
            colour = "#2e7d32"
        elif ok is False:
            colour = "#c62828"
        else:
            colour = "#555"
        self._status_label.setStyleSheet(f"color: {colour};")
        self._status_label.setText(message)
