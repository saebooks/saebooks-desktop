"""Tests for the first-run wizard ServerConnectPage.

Three transport modes are exercised:

- Local Docker (default) — auto-fills localhost REST + gRPC, prefers gRPC.
- Cloud URL — REST-only.  gRPC is intentionally not probed in this mode.
- LAN — both REST + gRPC; gRPC is preferred when reachable.

HTTP and gRPC calls are mocked so no real server is needed.
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


def _patch_httpx_ok(status_code: int = 200):
    """Return a context manager that patches httpx.Client to return *status_code*."""
    mock_response = MagicMock()
    mock_response.status_code = status_code

    mock_httpx = patch("saebooks_desktop.wizard.pages.server_connect.httpx")
    return mock_httpx, mock_response


def _install_mock_httpx(mock_httpx_module, mock_response, transport_error=ConnectionError):
    """Wire a MagicMock httpx module to return *mock_response* on Client.get()."""
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_response
    mock_httpx_module.Client.return_value = mock_client
    mock_httpx_module.TransportError = transport_error


# ============================================================================
# Structure
# ============================================================================


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

    def test_three_radios_exist(self, qapp) -> None:
        page = _make_page()
        assert hasattr(page, "_radio_local")
        assert hasattr(page, "_radio_cloud")
        assert hasattr(page, "_radio_lan")

    def test_legacy_remote_alias_points_at_cloud(self, qapp) -> None:
        """``_radio_remote`` keeps existing references working."""
        page = _make_page()
        assert page._radio_remote is page._radio_cloud

    def test_cloud_frame_hidden_in_local_mode(self, qapp) -> None:
        page = _make_page()
        assert not page._cloud_frame.isVisibleTo(page)

    def test_cloud_frame_visible_when_cloud_selected(self, qapp) -> None:
        page = _make_page()
        page.show()
        page._radio_cloud.setChecked(True)
        assert page._cloud_frame.isVisibleTo(page)
        page.hide()

    def test_lan_frame_visible_when_lan_selected(self, qapp) -> None:
        page = _make_page()
        page.show()
        page._radio_lan.setChecked(True)
        assert page._lan_frame.isVisibleTo(page)
        page.hide()

    def test_lan_persuasion_note_present(self, qapp) -> None:
        """The LAN-mode note must mention 'gRPC' and 'faster' to persuade users."""
        page = _make_page()
        text = page._lan_note.text().lower()
        assert "grpc" in text
        assert "faster" in text

    def test_not_complete_before_test(self, qapp) -> None:
        page = _make_page()
        assert not page.isComplete()

    def test_selected_mode_default_local(self, qapp) -> None:
        page = _make_page()
        assert page.selected_mode() == "local"


# ============================================================================
# Local Docker mode
# ============================================================================


class TestServerConnectLocalMode:
    def test_resolved_url_is_localhost(self, qapp) -> None:
        page = _make_page()
        assert page.resolved_url() == "http://localhost:8042"

    def test_resolved_grpc_target_is_localhost_50051(self, qapp) -> None:
        page = _make_page()
        assert page.resolved_grpc_target() == ("localhost", 50051)

    def test_test_connection_success_marks_complete(self, qapp) -> None:
        page = _make_page()
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("saebooks_desktop.wizard.pages.server_connect.httpx") as mock_httpx, patch(
            "saebooks_desktop.services.grpc_client.GrpcClient"
        ) as MockGrpc:
            _install_mock_httpx(mock_httpx, mock_response)
            MockGrpc.return_value.is_reachable.return_value = True

            page._on_test_clicked()

        assert page.isComplete()

    def test_test_connection_persists_url_on_success(self, qapp) -> None:
        page = _make_page()
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("saebooks_desktop.wizard.pages.server_connect.httpx") as mock_httpx, patch(
            "saebooks_desktop.services.grpc_client.GrpcClient"
        ) as MockGrpc:
            _install_mock_httpx(mock_httpx, mock_response)
            MockGrpc.return_value.is_reachable.return_value = True

            page._on_test_clicked()

        from saebooks_desktop.services.settings import (
            get_prefer_grpc,
            get_server_url,
            get_transport_mode,
        )
        assert get_server_url() == "http://localhost:8042"
        assert get_transport_mode() == "local"
        assert get_prefer_grpc() is True

    def test_grpc_unreachable_falls_back_to_rest_and_persists(self, qapp) -> None:
        """If gRPC probe fails the page still completes (REST fallback)."""
        page = _make_page()
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("saebooks_desktop.wizard.pages.server_connect.httpx") as mock_httpx, patch(
            "saebooks_desktop.services.grpc_client.GrpcClient"
        ) as MockGrpc:
            _install_mock_httpx(mock_httpx, mock_response)
            MockGrpc.return_value.is_reachable.return_value = False

            page._on_test_clicked()

        assert page.isComplete()
        from saebooks_desktop.services.settings import get_prefer_grpc
        assert get_prefer_grpc() is False


# ============================================================================
# Cloud / Remote URL mode
# ============================================================================


class TestServerConnectCloudMode:
    def test_resolved_url_uses_input_text(self, qapp) -> None:
        page = _make_page()
        page._radio_cloud.setChecked(True)
        page._url_input.setText("https://saebooks.example.com")
        assert page.resolved_url() == "https://saebooks.example.com"

    def test_cloud_resolved_grpc_target_is_none(self, qapp) -> None:
        """Cloud mode never uses gRPC."""
        page = _make_page()
        page._radio_cloud.setChecked(True)
        page._url_input.setText("https://saebooks.example.com")
        assert page.resolved_grpc_target() is None

    def test_cloud_success_persists_rest_only(self, qapp) -> None:
        page = _make_page()
        page._radio_cloud.setChecked(True)
        page._url_input.setText("https://saebooks.example.com")

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("saebooks_desktop.wizard.pages.server_connect.httpx") as mock_httpx:
            _install_mock_httpx(mock_httpx, mock_response)
            page._on_test_clicked()

        assert page.isComplete()
        from saebooks_desktop.services.settings import (
            get_grpc_url,
            get_prefer_grpc,
            get_server_url,
            get_transport_mode,
        )
        assert get_server_url() == "https://saebooks.example.com"
        assert get_grpc_url() == ""
        assert get_transport_mode() == "cloud"
        assert get_prefer_grpc() is False

    def test_test_connection_failure_not_complete(self, qapp) -> None:
        page = _make_page()
        page._radio_cloud.setChecked(True)
        page._url_input.setText("https://saebooks.example.com")

        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch("saebooks_desktop.wizard.pages.server_connect.httpx") as mock_httpx:
            _install_mock_httpx(mock_httpx, mock_response)
            page._on_test_clicked()

        assert not page.isComplete()

    def test_transport_error_shows_message_and_not_complete(self, qapp) -> None:
        page = _make_page()
        page._radio_cloud.setChecked(True)
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
        text = page._status_label.text().lower()
        assert "could not reach" in text or "error" in text

    def test_empty_url_rejected(self, qapp) -> None:
        page = _make_page()
        page._radio_cloud.setChecked(True)
        page._url_input.setText("")
        page._on_test_clicked()
        assert not page.isComplete()
        assert "url" in page._status_label.text().lower()


# ============================================================================
# LAN mode (REST + gRPC, gRPC preferred)
# ============================================================================


class TestServerConnectLanMode:
    def test_lan_grpc_target_parses_host_port(self, qapp) -> None:
        page = _make_page()
        page._radio_lan.setChecked(True)
        page._lan_grpc_input.setText("books.lan:50051")
        assert page.resolved_grpc_target() == ("books.lan", 50051)

    def test_lan_grpc_target_defaults_port_when_missing(self, qapp) -> None:
        page = _make_page()
        page._radio_lan.setChecked(True)
        page._lan_grpc_input.setText("books.lan")
        assert page.resolved_grpc_target() == ("books.lan", 50051)

    def test_lan_grpc_target_none_when_blank(self, qapp) -> None:
        page = _make_page()
        page._radio_lan.setChecked(True)
        page._lan_grpc_input.setText("")
        assert page.resolved_grpc_target() is None

    def test_lan_success_persists_both_urls_and_prefers_grpc(self, qapp) -> None:
        page = _make_page()
        page._radio_lan.setChecked(True)
        page._lan_rest_input.setText("http://books.lan:8042")
        page._lan_grpc_input.setText("books.lan:50051")

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("saebooks_desktop.wizard.pages.server_connect.httpx") as mock_httpx, patch(
            "saebooks_desktop.services.grpc_client.GrpcClient"
        ) as MockGrpc:
            _install_mock_httpx(mock_httpx, mock_response)
            MockGrpc.return_value.is_reachable.return_value = True

            page._on_test_clicked()

        assert page.isComplete()
        from saebooks_desktop.services.settings import (
            get_grpc_url,
            get_prefer_grpc,
            get_server_url,
            get_transport_mode,
        )
        assert get_server_url() == "http://books.lan:8042"
        assert get_grpc_url() == "grpc://books.lan:50051"
        assert get_transport_mode() == "lan"
        assert get_prefer_grpc() is True

    def test_lan_grpc_unreachable_demotes_prefer_grpc(self, qapp) -> None:
        page = _make_page()
        page._radio_lan.setChecked(True)
        page._lan_rest_input.setText("http://books.lan:8042")
        page._lan_grpc_input.setText("books.lan:50051")

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("saebooks_desktop.wizard.pages.server_connect.httpx") as mock_httpx, patch(
            "saebooks_desktop.services.grpc_client.GrpcClient"
        ) as MockGrpc:
            _install_mock_httpx(mock_httpx, mock_response)
            MockGrpc.return_value.is_reachable.return_value = False

            page._on_test_clicked()

        # REST works → page is complete, but gRPC was unreachable so we don't
        # prefer it (REST fallback).
        assert page.isComplete()
        from saebooks_desktop.services.settings import get_prefer_grpc, get_transport_mode
        assert get_transport_mode() == "lan"
        assert get_prefer_grpc() is False

    def test_lan_missing_grpc_target_rejected(self, qapp) -> None:
        page = _make_page()
        page._radio_lan.setChecked(True)
        page._lan_rest_input.setText("http://books.lan:8042")
        page._lan_grpc_input.setText("")
        page._on_test_clicked()
        assert not page.isComplete()
        assert "grpc" in page._status_label.text().lower()

    def test_lan_missing_rest_url_rejected(self, qapp) -> None:
        page = _make_page()
        page._radio_lan.setChecked(True)
        page._lan_rest_input.setText("")
        page._lan_grpc_input.setText("books.lan:50051")
        page._on_test_clicked()
        assert not page.isComplete()
