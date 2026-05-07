"""Tests for the first-run wizard ServerConnectPage.

HTTP calls are mocked so no real server is needed.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

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
    monkeypatch.setenv("SAEBOOKS_API_URL", "")
    yield
    s = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "SAE Engineering", "SAE Books")
    s.clear()
    s.sync()


def _make_page():
    from saebooks_desktop.wizard.pages.server_connect import ServerConnectPage
    return ServerConnectPage()


class TestServerConnectPageStructure:
    def test_instantiates(self, qapp) -> None:
        page = _make_page()
        assert page is not None

    def test_title_mentions_server(self, qapp) -> None:
        page = _make_page()
        assert "server" in page.title().lower() or "connect" in page.title().lower()

    def test_local_radio_checked_by_default(self, qapp) -> None:
        page = _make_page()
        assert page._radio_local.isChecked()

    def test_remote_url_input_disabled_in_local_mode(self, qapp) -> None:
        page = _make_page()
        assert not page._url_input.isEnabled()

    def test_remote_url_input_enabled_when_remote_selected(self, qapp) -> None:
        page = _make_page()
        page._radio_remote.setChecked(True)
        assert page._url_input.isEnabled()

    def test_not_complete_before_test(self, qapp) -> None:
        page = _make_page()
        assert not page.isComplete()


class TestServerConnectLocalMode:
    def test_resolved_url_is_localhost_in_local_mode(self, qapp) -> None:
        page = _make_page()
        assert page.resolved_url() == "http://localhost:8042"

    def test_test_connection_success_marks_complete(self, qapp) -> None:
        page = _make_page()
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("saebooks_desktop.wizard.pages.server_connect.httpx") as mock_httpx:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_httpx.Client.return_value = mock_client
            mock_httpx.TransportError = Exception  # make isinstance check work

            page._on_test_clicked()

        assert page.isComplete()

    def test_test_connection_persists_url_on_success(self, qapp, isolated_settings) -> None:
        page = _make_page()
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("saebooks_desktop.wizard.pages.server_connect.httpx") as mock_httpx:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_httpx.Client.return_value = mock_client
            mock_httpx.TransportError = Exception

            page._on_test_clicked()

        from saebooks_desktop.services.settings import get_server_url
        assert get_server_url() == "http://localhost:8042"


class TestServerConnectRemoteMode:
    def test_resolved_url_uses_input_text(self, qapp) -> None:
        page = _make_page()
        page._radio_remote.setChecked(True)
        page._url_input.setText("https://saebooks.example.com")
        assert page.resolved_url() == "https://saebooks.example.com"

    def test_test_connection_failure_not_complete(self, qapp) -> None:
        page = _make_page()
        page._radio_remote.setChecked(True)
        page._url_input.setText("https://saebooks.example.com")

        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch("saebooks_desktop.wizard.pages.server_connect.httpx") as mock_httpx:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_httpx.Client.return_value = mock_client
            mock_httpx.TransportError = ConnectionError

            page._on_test_clicked()

        assert not page.isComplete()

    def test_transport_error_shows_message_and_not_complete(self, qapp) -> None:
        page = _make_page()
        page._radio_remote.setChecked(True)
        page._url_input.setText("https://unreachable.example.com")

        with patch("saebooks_desktop.wizard.pages.server_connect.httpx") as mock_httpx:
            mock_httpx.TransportError = ConnectionError

            class _FakeClient:
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    return False
                def get(self, *a, **kw):
                    raise ConnectionError("no route to host")

            mock_httpx.Client.return_value = _FakeClient()
            page._on_test_clicked()

        assert not page.isComplete()
        assert "Could not reach" in page._status_label.text() or "error" in page._status_label.text().lower()
