"""First-run wizard — Page 3: Sign in.

Two paths:

1. **Email + password** (default).  Posts credentials to
   ``POST /api/v1/auth/login`` and stores the returned bearer token.
   This is the path for users with an existing account.

2. **Paste bearer token**.  Toggle on the radio "I have a bearer token
   from ``bootstrap-admin``".  The token is validated by calling
   ``GET /api/v1/me`` with it in the Authorization header.  This is the
   first-run path on a fresh self-hosted install: the user runs
   ``python -m saebooks.cli bootstrap-admin --email you@example.com``,
   copies the printed JWT, and pastes it here.  No password is set on
   the account yet — it gets set later via the change-password flow.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWizardPage,
)


class SignInPage(QWizardPage):
    """Wizard page for email+password OR bearer-token paste authentication."""

    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.setTitle("Sign in")
        self.setSubTitle(
            "Sign in with your email + password, or paste the bearer "
            "token printed by bootstrap-admin on a fresh install."
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(8)

        # ------------------------------------------------------------------
        # Mode radios
        # ------------------------------------------------------------------
        self._radio_password = QRadioButton(
            "Email + password (existing account)"
        )
        self._radio_token = QRadioButton(
            "I have a bearer token from bootstrap-admin (first-time setup)"
        )
        self._radio_password.setChecked(True)

        self._btn_group = QButtonGroup(self)
        self._btn_group.addButton(self._radio_password)
        self._btn_group.addButton(self._radio_token)

        layout.addWidget(self._radio_password)
        layout.addWidget(self._radio_token)

        # ------------------------------------------------------------------
        # Password form
        # ------------------------------------------------------------------
        self._password_frame = QFrame()
        password_layout = QFormLayout(self._password_frame)
        password_layout.setContentsMargins(20, 4, 0, 4)

        self._email_input = QLineEdit()
        self._email_input.setPlaceholderText("you@example.com")
        password_layout.addRow("Email:", self._email_input)

        self._password_input = QLineEdit()
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_input.setPlaceholderText("••••••••")
        password_layout.addRow("Password:", self._password_input)
        layout.addWidget(self._password_frame)

        # ------------------------------------------------------------------
        # Token form
        # ------------------------------------------------------------------
        self._token_frame = QFrame()
        token_layout = QFormLayout(self._token_frame)
        token_layout.setContentsMargins(20, 4, 0, 4)

        self._token_input = QLineEdit()
        self._token_input.setPlaceholderText("eyJhbGciOi…")
        # Don't echo as a password — bearer tokens benefit from being visible
        # so the user can verify the paste was clean.
        token_layout.addRow("Bearer token:", self._token_input)

        token_hint = QLabel(
            "Paste the JWT printed by\n"
            "  python -m saebooks.cli bootstrap-admin --email you@example.com\n"
            "It's valid for 30 days; you can change your password later."
        )
        token_hint.setWordWrap(True)
        token_hint.setStyleSheet("color: #555; font-size: 11px;")
        token_layout.addRow(token_hint)
        layout.addWidget(self._token_frame)

        # ------------------------------------------------------------------
        # Submit + status
        # ------------------------------------------------------------------
        self._sign_in_btn = QPushButton("Sign In")
        self._sign_in_btn.clicked.connect(self._on_sign_in_clicked)
        layout.addWidget(self._sign_in_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        layout.addStretch()

        self._login_ok = False

        # Connections
        self._radio_password.toggled.connect(self._on_mode_changed)
        self._radio_token.toggled.connect(self._on_mode_changed)

        # Initial visibility
        self._on_mode_changed()

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

    def _on_mode_changed(self) -> None:
        token_mode = self._radio_token.isChecked()
        self._password_frame.setVisible(not token_mode)
        self._token_frame.setVisible(token_mode)
        self._login_ok = False
        self._status_label.setText("")
        self.completeChanged.emit()

    def _on_sign_in_clicked(self) -> None:
        if self._radio_token.isChecked():
            self._sign_in_with_token()
        else:
            self._sign_in_with_password()

    # ------------------------------------------------------------------
    # Email + password path
    # ------------------------------------------------------------------

    def _sign_in_with_password(self) -> None:
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
        from saebooks_desktop.services.settings import get_server_url, set_auth_token

        from saebooks_desktop.services.api_client import APIClient

        base_url = get_server_url() or "http://localhost:8042"
        client = APIClient(base_url=base_url)

        try:
            token = login(client, email, password)
        except Exception as exc:  # noqa: BLE001
            self._set_status(False, str(exc))
            self._sign_in_btn.setEnabled(True)
            return

        set_auth_token(token)
        self._login_ok = True
        self._set_status(True, "Signed in successfully.")
        self._sign_in_btn.setEnabled(True)
        self.completeChanged.emit()

    # ------------------------------------------------------------------
    # Bearer-token path
    # ------------------------------------------------------------------

    def _sign_in_with_token(self) -> None:
        token = self._token_input.text().strip()
        if not token:
            self._set_status(False, "Token is required.")
            return

        self._sign_in_btn.setEnabled(False)
        self._set_status(None, "Validating token…")

        from saebooks_desktop.services.api_client import APIClient
        from saebooks_desktop.services.auth import validate_token
        from saebooks_desktop.services.settings import get_server_url, set_auth_token

        base_url = get_server_url() or "http://localhost:8042"
        client = APIClient(base_url=base_url)

        try:
            user = validate_token(client, token)
        except Exception as exc:  # noqa: BLE001
            self._set_status(False, str(exc))
            self._sign_in_btn.setEnabled(True)
            return

        set_auth_token(token)
        self._login_ok = True
        email = user.get("email") if isinstance(user, dict) else None
        if email:
            self._set_status(True, f"Token accepted — signed in as {email}.")
        else:
            self._set_status(True, "Token accepted.")
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
