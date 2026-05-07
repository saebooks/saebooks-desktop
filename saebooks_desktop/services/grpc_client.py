"""gRPC transport client for saebooks-api.

The desktop uses gRPC (port 50051) as its primary transport when the server
supports it, falling back to REST (APIClient/httpx) when unavailable.

Uses ``grpc.insecure_channel`` for local/dev connections.  TLS channel
credentials can be injected via the ``tls`` constructor parameter for
production deployments.

Usage::

    client = GrpcClient(host="localhost", port=50051, auth_token="secret")
    if client.is_reachable():
        contacts = client.list_contacts(page_size=50)
    stop = client.watch_changes(cursor=0, callback=my_cb)
    # ... later ...
    stop()
    client.close()
"""
from __future__ import annotations

import threading
from typing import Any, Callable

import grpc

from saebooks_desktop.grpc_gen import saebooks_pb2, saebooks_pb2_grpc

# Default gRPC port matching the API rebuild plan.
DEFAULT_GRPC_PORT = 50051
# Deadline used for the reachability probe.
_PROBE_DEADLINE_S = 2.0
# Deadline for regular RPCs.
_RPC_DEADLINE_S = 10.0


def _contact_to_dict(record: saebooks_pb2.ContactRecord) -> dict[str, Any]:  # type: ignore[name-defined]
    """Convert a ContactRecord proto message to a plain dict."""
    return {
        "id": record.id,
        "name": record.name,
        "email": record.email or None,
        "phone": record.phone or None,
        "version": record.version,
        "updated_at": record.updated_at or None,
    }


class GrpcClient:
    """gRPC client wrapping the SAEBooks service stub.

    Parameters
    ----------
    host:
        Hostname or IP of the saebooks-api gRPC endpoint.
    port:
        gRPC port (default 50051).
    auth_token:
        Bearer token injected as ``authorization`` gRPC metadata on every call.
    tls:
        If ``None`` (default) use ``grpc.insecure_channel`` for local dev.
        Pass a ``grpc.ChannelCredentials`` instance for production TLS.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = DEFAULT_GRPC_PORT,
        auth_token: str = "",
        tls: grpc.ChannelCredentials | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._auth_token = auth_token
        self._target = f"{host}:{port}"

        if tls is not None:
            self._channel = grpc.secure_channel(self._target, tls)
        else:
            self._channel = grpc.insecure_channel(self._target)
        self._stub = saebooks_pb2_grpc.SAEBooksStub(self._channel)

    # ------------------------------------------------------------------
    # Metadata helpers
    # ------------------------------------------------------------------

    def _metadata(self) -> list[tuple[str, str]]:
        """Return gRPC call metadata with Authorization header."""
        if self._auth_token:
            return [("authorization", f"Bearer {self._auth_token}")]
        return []

    # ------------------------------------------------------------------
    # Connectivity probe
    # ------------------------------------------------------------------

    def is_reachable(self, timeout: float = _PROBE_DEADLINE_S) -> bool:
        """Return True if the gRPC endpoint responds within *timeout* seconds.

        Uses a Heartbeat RPC with an empty JWT.  The server will reject it
        with UNAUTHENTICATED, but a response of *any* kind proves connectivity.
        DEADLINE_EXCEEDED or UNAVAILABLE indicates the server is not reachable.
        """
        try:
            self._stub.Heartbeat(
                saebooks_pb2.HeartbeatRequest(licence_jwt=""),
                timeout=timeout,
                metadata=self._metadata(),
            )
            return True
        except grpc.RpcError as exc:
            code = exc.code()  # type: ignore[attr-defined]
            # UNAUTHENTICATED means the server responded — it's reachable.
            if code == grpc.StatusCode.UNAUTHENTICATED:
                return True
            # UNIMPLEMENTED means the method is missing but gRPC is running.
            if code == grpc.StatusCode.UNIMPLEMENTED:
                return True
            # DEADLINE_EXCEEDED / UNAVAILABLE / UNKNOWN → not reachable.
            return False
        except Exception:  # noqa: BLE001
            return False

    # ------------------------------------------------------------------
    # Contacts RPCs
    # ------------------------------------------------------------------

    def list_contacts(self, page_size: int = 100) -> list[dict[str, Any]]:
        """Call ListContacts and return a list of contact dicts.

        Raises:
            grpc.RpcError: propagated as-is so callers can inspect the status.
        """
        req = saebooks_pb2.ListContactsRequest(
            page=saebooks_pb2.PageRequest(page=1, page_size=page_size),
        )
        resp = self._stub.ListContacts(
            req,
            timeout=_RPC_DEADLINE_S,
            metadata=self._metadata(),
        )
        return [_contact_to_dict(c) for c in resp.contacts]

    def get_contact(self, id: str) -> dict[str, Any]:
        """Call GetContact and return the contact as a plain dict.

        Raises:
            grpc.RpcError: propagated as-is.
        """
        req = saebooks_pb2.GetContactRequest(id=id)
        resp = self._stub.GetContact(
            req,
            timeout=_RPC_DEADLINE_S,
            metadata=self._metadata(),
        )
        return _contact_to_dict(resp.contact)

    def create_contact(self, contact: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """Call CreateContact and return (status_code_equivalent, dict).

        Returns 201 on success, 409 if a conflict is indicated by the server.

        Raises:
            grpc.RpcError: for errors other than ALREADY_EXISTS.
        """
        req = saebooks_pb2.CreateContactRequest(
            name=contact.get("name", ""),
            email=contact.get("email", ""),
            phone=contact.get("phone", ""),
        )
        try:
            resp = self._stub.CreateContact(
                req,
                timeout=_RPC_DEADLINE_S,
                metadata=self._metadata(),
            )
            return 201, _contact_to_dict(resp.contact)
        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.ALREADY_EXISTS:  # type: ignore[attr-defined]
                return 409, {"error": exc.details()}  # type: ignore[attr-defined]
            raise

    def update_contact(
        self, id: str, contact: dict[str, Any], if_match_version: int
    ) -> tuple[int, dict[str, Any]]:
        """Call UpdateContact and return (status_code_equivalent, dict).

        Returns 200 on success, 409 on version conflict.

        Raises:
            grpc.RpcError: for errors other than ABORTED (version conflict).
        """
        req = saebooks_pb2.UpdateContactRequest(
            id=id,
            name=contact.get("name", ""),
            email=contact.get("email", ""),
            phone=contact.get("phone", ""),
            if_match_version=if_match_version,
        )
        try:
            resp = self._stub.UpdateContact(
                req,
                timeout=_RPC_DEADLINE_S,
                metadata=self._metadata(),
            )
            return 200, _contact_to_dict(resp.contact)
        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.ABORTED:  # type: ignore[attr-defined]
                return 409, {"error": exc.details()}  # type: ignore[attr-defined]
            raise

    # ------------------------------------------------------------------
    # Streaming RPC — WatchChanges
    # ------------------------------------------------------------------

    def watch_changes(self, since_cursor: int = 0):
        """Generator yielding change event dicts from the WatchChanges stream.

        Yields dicts with keys: entity, entity_id, op, cursor, payload_json,
        version — matching the REST /api/v1/changes item shape.

        Raises:
            grpc.RpcError: if the stream fails with an unexpected status code.
        """
        req = saebooks_pb2.WatchChangesRequest(cursor=since_cursor)
        call = self._stub.WatchChanges(
            req,
            metadata=self._metadata(),
        )
        for event in call:
            yield {
                "entity": event.entity,
                "entity_id": event.entity_id,
                "op": event.op,
                "cursor": event.cursor,
                "payload_json": event.payload_json,
                "version": event.version,
            }

    def watch_changes_async(
        self,
        cursor: int,
        callback: Callable[[dict[str, Any]], None],
    ) -> Callable[[], None]:
        """Open the WatchChanges server-streaming RPC in a background thread.

        Parameters
        ----------
        cursor:
            Resume streaming from this change-log cursor (0 = from the start).
        callback:
            Called for each ``ChangeEvent`` received.  The argument is a plain
            dict with keys: ``entity``, ``entity_id``, ``op``, ``cursor``,
            ``payload_json``, ``version``.

        Returns
        -------
        stop:
            A zero-argument callable that cancels the stream and joins the
            background thread.
        """
        stop_event = threading.Event()

        def _run() -> None:
            req = saebooks_pb2.WatchChangesRequest(cursor=cursor)
            try:
                call = self._stub.WatchChanges(
                    req,
                    metadata=self._metadata(),
                )
                for event in call:
                    if stop_event.is_set():
                        break
                    callback(
                        {
                            "entity": event.entity,
                            "entity_id": event.entity_id,
                            "op": event.op,
                            "cursor": event.cursor,
                            "payload_json": event.payload_json,
                            "version": event.version,
                        }
                    )
            except grpc.RpcError as exc:
                if exc.code() not in (  # type: ignore[attr-defined]
                    grpc.StatusCode.CANCELLED,
                    grpc.StatusCode.UNAVAILABLE,
                ):
                    pass
            except Exception:  # noqa: BLE001
                pass

        thread = threading.Thread(target=_run, daemon=True, name="grpc-watch")
        thread.start()

        def _stop() -> None:
            stop_event.set()
            thread.join(timeout=3.0)

        return _stop

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying gRPC channel."""
        self._channel.close()

    def __enter__(self) -> "GrpcClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
