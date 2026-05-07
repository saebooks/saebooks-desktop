"""Tests for gRPC transport client and transport selector.

All tests run offscreen and without a real gRPC server — stubs are mocked
where a live connection would be required.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

# Force offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


import pytest


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# GrpcClient instantiation
# ---------------------------------------------------------------------------


class TestGrpcClientInstantiation:
    def test_instantiates_without_crash(self) -> None:
        """GrpcClient must construct without raising (channel only, no server)."""
        from saebooks_desktop.services.grpc_client import GrpcClient

        client = GrpcClient(host="127.0.0.1", port=50051, auth_token="x")
        assert client is not None
        client.close()

    def test_target_string(self) -> None:
        """Internal target must be host:port."""
        from saebooks_desktop.services.grpc_client import GrpcClient

        client = GrpcClient(host="127.0.0.1", port=50051, auth_token="tok")
        assert client._target == "127.0.0.1:50051"
        client.close()

    def test_context_manager(self) -> None:
        """GrpcClient must work as a context manager without crashing."""
        from saebooks_desktop.services.grpc_client import GrpcClient

        with GrpcClient(host="127.0.0.1", port=50051, auth_token="x") as client:
            assert client is not None

    def test_metadata_with_token(self) -> None:
        """_metadata() must return Authorization bearer entry when token set."""
        from saebooks_desktop.services.grpc_client import GrpcClient

        client = GrpcClient(host="127.0.0.1", port=50051, auth_token="secret")
        meta = client._metadata()
        assert ("authorization", "Bearer secret") in meta
        client.close()

    def test_metadata_empty_without_token(self) -> None:
        """_metadata() must return empty list when no token set."""
        from saebooks_desktop.services.grpc_client import GrpcClient

        client = GrpcClient(host="127.0.0.1", port=50051, auth_token="")
        meta = client._metadata()
        assert meta == []
        client.close()


# ---------------------------------------------------------------------------
# is_reachable — nothing listening on the port
# ---------------------------------------------------------------------------


class TestGrpcClientIsReachable:
    def test_returns_false_when_nothing_listening(self) -> None:
        """is_reachable() must return False (not raise) when no server is up."""
        from saebooks_desktop.services.grpc_client import GrpcClient

        # Port 50052 should not have anything listening in the test env.
        client = GrpcClient(host="127.0.0.1", port=50052, auth_token="x")
        result = client.is_reachable(timeout=0.5)
        assert result is False
        client.close()

    def test_returns_true_when_unauthenticated(self) -> None:
        """is_reachable() must return True when server replies UNAUTHENTICATED."""
        import grpc
        from saebooks_desktop.services.grpc_client import GrpcClient

        client = GrpcClient(host="127.0.0.1", port=50051, auth_token="x")

        rpc_error = grpc.RpcError()
        rpc_error.code = lambda: grpc.StatusCode.UNAUTHENTICATED  # type: ignore[method-assign]
        client._stub = MagicMock()
        client._stub.Heartbeat.side_effect = rpc_error

        assert client.is_reachable() is True
        client.close()

    def test_returns_true_when_unimplemented(self) -> None:
        """is_reachable() must return True when server replies UNIMPLEMENTED."""
        import grpc
        from saebooks_desktop.services.grpc_client import GrpcClient

        client = GrpcClient(host="127.0.0.1", port=50051, auth_token="x")

        rpc_error = grpc.RpcError()
        rpc_error.code = lambda: grpc.StatusCode.UNIMPLEMENTED  # type: ignore[method-assign]
        client._stub = MagicMock()
        client._stub.Heartbeat.side_effect = rpc_error

        assert client.is_reachable() is True
        client.close()

    def test_returns_false_on_arbitrary_exception(self) -> None:
        """is_reachable() must return False on any non-gRPC exception."""
        from saebooks_desktop.services.grpc_client import GrpcClient

        client = GrpcClient(host="127.0.0.1", port=50051, auth_token="x")
        client._stub = MagicMock()
        client._stub.Heartbeat.side_effect = RuntimeError("boom")

        assert client.is_reachable() is False
        client.close()


# ---------------------------------------------------------------------------
# list_contacts — mocked stub
# ---------------------------------------------------------------------------


class TestGrpcClientListContacts:
    def test_returns_list_of_dicts(self) -> None:
        """list_contacts() with a mocked stub returns expected list[dict]."""
        from saebooks_desktop.grpc_gen import saebooks_pb2
        from saebooks_desktop.services.grpc_client import GrpcClient

        client = GrpcClient(host="127.0.0.1", port=50051, auth_token="x")

        # Build proto response with two contacts.
        c1 = saebooks_pb2.ContactRecord(
            id="1", name="Alice", email="alice@example.com", phone="", version=1
        )
        c2 = saebooks_pb2.ContactRecord(
            id="2", name="Bob", email="bob@example.com", phone="555-0100", version=2
        )
        mock_resp = saebooks_pb2.ListContactsResponse(contacts=[c1, c2])
        client._stub = MagicMock()
        client._stub.ListContacts.return_value = mock_resp

        result = client.list_contacts(page_size=50)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["name"] == "Alice"
        assert result[0]["email"] == "alice@example.com"
        assert result[1]["name"] == "Bob"
        assert result[1]["phone"] == "555-0100"
        client.close()

    def test_empty_response(self) -> None:
        """list_contacts() with empty server response returns empty list."""
        from saebooks_desktop.grpc_gen import saebooks_pb2
        from saebooks_desktop.services.grpc_client import GrpcClient

        client = GrpcClient(host="127.0.0.1", port=50051, auth_token="x")
        client._stub = MagicMock()
        client._stub.ListContacts.return_value = saebooks_pb2.ListContactsResponse(
            contacts=[]
        )

        result = client.list_contacts()
        assert result == []
        client.close()


# ---------------------------------------------------------------------------
# get_contact — mocked stub
# ---------------------------------------------------------------------------


class TestGrpcClientGetContact:
    def test_returns_dict_with_expected_fields(self) -> None:
        """get_contact() returns a plain dict for the requested contact."""
        from saebooks_desktop.grpc_gen import saebooks_pb2
        from saebooks_desktop.services.grpc_client import GrpcClient

        client = GrpcClient(host="127.0.0.1", port=50051, auth_token="x")
        contact = saebooks_pb2.ContactRecord(
            id="abc", name="Carol", email="carol@example.com", phone="", version=3
        )
        client._stub = MagicMock()
        client._stub.GetContact.return_value = saebooks_pb2.ContactResponse(
            contact=contact
        )

        result = client.get_contact("abc")
        assert result["id"] == "abc"
        assert result["name"] == "Carol"
        assert result["version"] == 3
        client.close()


# ---------------------------------------------------------------------------
# create_contact — mocked stub
# ---------------------------------------------------------------------------


class TestGrpcClientCreateContact:
    def test_returns_201_on_success(self) -> None:
        """create_contact() returns (201, dict) on success."""
        from saebooks_desktop.grpc_gen import saebooks_pb2
        from saebooks_desktop.services.grpc_client import GrpcClient

        client = GrpcClient(host="127.0.0.1", port=50051, auth_token="x")
        contact = saebooks_pb2.ContactRecord(
            id="new-1", name="Dave", email="dave@example.com", phone="", version=1
        )
        client._stub = MagicMock()
        client._stub.CreateContact.return_value = saebooks_pb2.ContactResponse(
            contact=contact
        )

        status, result = client.create_contact(
            {"name": "Dave", "email": "dave@example.com"}
        )
        assert status == 201
        assert result["name"] == "Dave"
        client.close()

    def test_returns_409_on_already_exists(self) -> None:
        """create_contact() returns (409, error_dict) on ALREADY_EXISTS."""
        import grpc
        from saebooks_desktop.services.grpc_client import GrpcClient

        client = GrpcClient(host="127.0.0.1", port=50051, auth_token="x")
        rpc_error = grpc.RpcError()
        rpc_error.code = lambda: grpc.StatusCode.ALREADY_EXISTS  # type: ignore[method-assign]
        rpc_error.details = lambda: "contact already exists"  # type: ignore[method-assign]
        client._stub = MagicMock()
        client._stub.CreateContact.side_effect = rpc_error

        status, result = client.create_contact({"name": "Dave"})
        assert status == 409
        assert "error" in result
        client.close()


# ---------------------------------------------------------------------------
# update_contact — mocked stub
# ---------------------------------------------------------------------------


class TestGrpcClientUpdateContact:
    def test_returns_200_on_success(self) -> None:
        """update_contact() returns (200, dict) on success."""
        from saebooks_desktop.grpc_gen import saebooks_pb2
        from saebooks_desktop.services.grpc_client import GrpcClient

        client = GrpcClient(host="127.0.0.1", port=50051, auth_token="x")
        updated = saebooks_pb2.ContactRecord(
            id="abc", name="Eve", email="eve@example.com", phone="", version=2
        )
        client._stub = MagicMock()
        client._stub.UpdateContact.return_value = saebooks_pb2.ContactResponse(
            contact=updated
        )

        status, result = client.update_contact(
            "abc", {"name": "Eve", "email": "eve@example.com"}, if_match_version=1
        )
        assert status == 200
        assert result["name"] == "Eve"
        assert result["version"] == 2
        client.close()

    def test_returns_409_on_version_conflict(self) -> None:
        """update_contact() returns (409, error_dict) on ABORTED (version conflict)."""
        import grpc
        from saebooks_desktop.services.grpc_client import GrpcClient

        client = GrpcClient(host="127.0.0.1", port=50051, auth_token="x")
        rpc_error = grpc.RpcError()
        rpc_error.code = lambda: grpc.StatusCode.ABORTED  # type: ignore[method-assign]
        rpc_error.details = lambda: "version conflict"  # type: ignore[method-assign]
        client._stub = MagicMock()
        client._stub.UpdateContact.side_effect = rpc_error

        status, result = client.update_contact(
            "abc", {"name": "Eve"}, if_match_version=1
        )
        assert status == 409
        assert "error" in result
        client.close()


# ---------------------------------------------------------------------------
# Transport selector
# ---------------------------------------------------------------------------


class TestTransportSelector:
    def test_rest_mode_returns_api_client(self, monkeypatch) -> None:
        """resolve_transport() returns APIClient when QSettings returns REST."""
        from saebooks_desktop.services.api_client import APIClient, TransportMode

        monkeypatch.setenv("SAEBOOKS_API_URL", "http://127.0.0.1:19999")
        monkeypatch.setenv("SAEBOOKS_API_TOKEN", "tok")

        with patch(
            "saebooks_desktop.services.api_client._read_transport_mode",
            return_value=TransportMode.REST,
        ):
            client = APIClient()
            transport = client.resolve_transport()

        assert transport is client  # REST returns self

    def test_auto_falls_back_to_rest_when_grpc_unreachable(
        self, monkeypatch
    ) -> None:
        """In AUTO mode, if gRPC is unreachable, resolve_transport() returns REST."""
        from saebooks_desktop.services.api_client import APIClient, TransportMode

        monkeypatch.setenv("SAEBOOKS_API_URL", "http://127.0.0.1:19999")
        monkeypatch.setenv("SAEBOOKS_API_TOKEN", "tok")

        mock_grpc = MagicMock()
        mock_grpc.is_reachable.return_value = False

        with patch(
            "saebooks_desktop.services.api_client._read_transport_mode",
            return_value=TransportMode.AUTO,
        ), patch(
            "saebooks_desktop.services.api_client._make_grpc_client",
            return_value=mock_grpc,
        ):
            client = APIClient()
            transport = client.resolve_transport()

        assert transport is client  # fell back to REST

    def test_auto_uses_grpc_when_reachable(self, monkeypatch) -> None:
        """In AUTO mode, if gRPC is reachable, resolve_transport() returns GrpcClient."""
        from saebooks_desktop.services.api_client import APIClient, TransportMode
        from saebooks_desktop.services.grpc_client import GrpcClient

        monkeypatch.setenv("SAEBOOKS_API_URL", "http://127.0.0.1:19999")
        monkeypatch.setenv("SAEBOOKS_API_TOKEN", "tok")

        mock_grpc = MagicMock(spec=GrpcClient)
        mock_grpc.is_reachable.return_value = True

        with patch(
            "saebooks_desktop.services.api_client._read_transport_mode",
            return_value=TransportMode.AUTO,
        ), patch(
            "saebooks_desktop.services.api_client._make_grpc_client",
            return_value=mock_grpc,
        ):
            client = APIClient()
            transport = client.resolve_transport()

        assert transport is mock_grpc

    def test_resolve_caches_result(self, monkeypatch) -> None:
        """resolve_transport() returns the same object on repeated calls."""
        from saebooks_desktop.services.api_client import APIClient, TransportMode

        monkeypatch.setenv("SAEBOOKS_API_URL", "http://127.0.0.1:19999")
        monkeypatch.setenv("SAEBOOKS_API_TOKEN", "tok")

        with patch(
            "saebooks_desktop.services.api_client._read_transport_mode",
            return_value=TransportMode.REST,
        ):
            client = APIClient()
            t1 = client.resolve_transport()
            t2 = client.resolve_transport()

        assert t1 is t2

    def test_grpc_mode_falls_back_to_rest_when_unreachable(
        self, monkeypatch
    ) -> None:
        """In GRPC mode, if gRPC is unreachable, resolve_transport() logs and falls back."""
        from saebooks_desktop.services.api_client import APIClient, TransportMode

        monkeypatch.setenv("SAEBOOKS_API_URL", "http://127.0.0.1:19999")
        monkeypatch.setenv("SAEBOOKS_API_TOKEN", "tok")

        mock_grpc = MagicMock()
        mock_grpc.is_reachable.return_value = False
        mock_grpc._target = "127.0.0.1:50051"

        with patch(
            "saebooks_desktop.services.api_client._read_transport_mode",
            return_value=TransportMode.GRPC,
        ), patch(
            "saebooks_desktop.services.api_client._make_grpc_client",
            return_value=mock_grpc,
        ):
            client = APIClient()
            transport = client.resolve_transport()

        assert transport is client  # fell back to REST


# ---------------------------------------------------------------------------
# Status bar transport label
# ---------------------------------------------------------------------------


class TestStatusBarTransportLabel:
    def test_main_window_has_transport_label(self, qapp) -> None:
        """MainWindow must expose a _transport_label widget on the status bar."""
        from saebooks_desktop.main_window import MainWindow

        window = MainWindow()
        assert hasattr(window, "_transport_label")
        assert window._transport_label is not None

    def test_transport_label_text_rest_or_grpc(self, qapp) -> None:
        """_transport_label text must be 'REST' or 'gRPC' (resolved at init)."""
        from saebooks_desktop.main_window import MainWindow

        window = MainWindow()
        label_text = window._transport_label.text()
        assert label_text in ("REST", "gRPC"), (
            f"Expected 'REST' or 'gRPC', got {label_text!r}"
        )

    def test_active_transport_name_property(self, monkeypatch) -> None:
        """active_transport_name returns 'REST' before resolve or after REST resolve."""
        from saebooks_desktop.services.api_client import APIClient

        monkeypatch.setenv("SAEBOOKS_API_URL", "http://127.0.0.1:19999")
        monkeypatch.setenv("SAEBOOKS_API_TOKEN", "tok")

        client = APIClient()
        # Before resolve: defaults to REST label.
        assert client.active_transport_name == "REST"
