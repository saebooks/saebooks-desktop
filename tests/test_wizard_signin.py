"""Tests for the first-run wizard SignInPage.

The auth.login service is mocked so no real API calls are made.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    from PySide6.QtCore import QSettings
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path)
    )
    monkeypatch.setenv("SAEBOOKS_API_URL", "http://localhost:8042")
    monkeypatch.setenv("SAEBOOKS_API_TOKEN", "")
    yield
    s = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "SAE Engineering", "SAE Books")
    s.clear()
    s.sync()


def _make_page():
    from saebooks_desktop.wizard.pages.sign_in import SignInPage
    return SignInPage()


class TestSignInPageStructure:
    def test_instantiates(self, qapp) -> None:
        page = _make_page()
        assert page is not None

    def test_has_email_input(self, qapp) -> None:
        from PySide6.QtWidgets import QLineEdit
        page = _make_page()
        assert isinstance(page._email_input, QLineEdit)

    def test_has_password_input(self, qapp) -> None:
        from PySide6.QtWidgets import QLineEdit
        page = _make_page()
        assert page._password_input.echoMode().value == 2  # Password mode

    def test_not_complete_on_init(self, qapp) -> None:
        page = _make_page()
        assert not page.isComplete()

    def test_empty_email_shows_error(self, qapp) -> None:
        page = _make_page()
        page._email_input.setText("")
        page._password_input.setText("secret")
        page._on_sign_in_clicked()
        assert not page.isComplete()
        assert "Email" in page._status_label.text()

    def test_empty_password_shows_error(self, qapp) -> None:
        page = _make_page()
        page._email_input.setText("user@example.com")
        page._password_input.setText("")
        page._on_sign_in_clicked()
        assert not page.isComplete()
        assert "Password" in page._status_label.text()


class TestSignInLoginFlow:
    def test_successful_login_saves_token(self, qapp, isolated_settings) -> None:
        page = _make_page()
        page._email_input.setText("user@example.com")
        page._password_input.setText("correct")

        with patch("saebooks_desktop.services.auth.login", return_value="tok_abc"):
            page._on_sign_in_clicked()

        assert page.isComplete()

        # Token should have been persisted to settings.
        # SAEBOOKS_API_TOKEN is set in the fixture env but set_auth_token
        # writes to QSettings; we verify via get_auth_token (env takes priority).
        # Force env to be empty so QSettings path is read.
        import os as _os
        orig = _os.environ.get("SAEBOOKS_API_TOKEN", None)
        try:
            _os.environ["SAEBOOKS_API_TOKEN"] = ""
            from saebooks_desktop.services import settings as sm
            assert sm.get_auth_token() == "tok_abc"
        finally:
            if orig is not None:
                _os.environ["SAEBOOKS_API_TOKEN"] = orig
            else:
                del _os.environ["SAEBOOKS_API_TOKEN"]

    def test_failed_login_shows_error_not_complete(self, qapp, isolated_settings) -> None:
        from saebooks_desktop.services.api_client import APIError
        page = _make_page()
        page._email_input.setText("user@example.com")
        page._password_input.setText("wrong")

        with patch(
            "saebooks_desktop.services.auth.login",
            side_effect=APIError("Invalid credentials", status_code=401),
        ):
            page._on_sign_in_clicked()

        assert not page.isComplete()
        assert "Invalid credentials" in page._status_label.text()

    def test_initialize_page_resets_state(self, qapp) -> None:
        page = _make_page()
        # Manually set as complete
        page._login_ok = True
        page._status_label.setText("previous status")
        page.initializePage()
        assert not page._login_ok
        assert page._status_label.text() == ""


class TestSignInTokenPath:
    """Bearer-token paste flow used immediately after `bootstrap-admin`."""

    def test_token_radio_present(self, qapp) -> None:
        page = _make_page()
        assert hasattr(page, "_radio_token")
        assert hasattr(page, "_radio_password")
        assert page._radio_password.isChecked()

    def test_token_input_field_present(self, qapp) -> None:
        from PySide6.QtWidgets import QLineEdit
        page = _make_page()
        assert isinstance(page._token_input, QLineEdit)

    def test_empty_token_shows_error(self, qapp) -> None:
        page = _make_page()
        page._radio_token.setChecked(True)
        page._token_input.setText("")
        page._on_sign_in_clicked()
        assert not page.isComplete()
        assert "token" in page._status_label.text().lower()

    def test_valid_token_completes_and_persists(self, qapp) -> None:
        page = _make_page()
        page._radio_token.setChecked(True)
        page._token_input.setText("eyJhbGc.payload.sig")

        with patch(
            "saebooks_desktop.services.auth.validate_token",
            return_value={"id": "u1", "email": "owner@example.com"},
        ):
            page._on_sign_in_clicked()

        assert page.isComplete()
        assert "owner@example.com" in page._status_label.text()

        import os as _os
        orig = _os.environ.get("SAEBOOKS_API_TOKEN", None)
        try:
            _os.environ["SAEBOOKS_API_TOKEN"] = ""
            from saebooks_desktop.services import settings as sm
            assert sm.get_auth_token() == "eyJhbGc.payload.sig"
        finally:
            if orig is not None:
                _os.environ["SAEBOOKS_API_TOKEN"] = orig
            else:
                _os.environ.pop("SAEBOOKS_API_TOKEN", None)

    def test_invalid_token_not_complete(self, qapp) -> None:
        from saebooks_desktop.services.api_client import APIError
        page = _make_page()
        page._radio_token.setChecked(True)
        page._token_input.setText("not-a-token")

        with patch(
            "saebooks_desktop.services.auth.validate_token",
            side_effect=APIError("Token rejected by server (401).", status_code=401),
        ):
            page._on_sign_in_clicked()

        assert not page.isComplete()
        assert "401" in page._status_label.text() or "rejected" in page._status_label.text().lower()
