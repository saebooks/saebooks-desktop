"""Tests for the SQLite cache, outbox, and SyncEngine.

All tests are offscreen-safe and use temporary SQLite files (tmp_path).
No live API server is required — api_client calls are mocked.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Ensure offscreen Qt platform before PySide6 import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    """Open a fresh in-memory-style DB via a temp file, tables created."""
    from saebooks_desktop.cache.db import get_connection, init_db

    conn = get_connection(db_path=tmp_path / "test_cache.db")
    init_db(conn)
    return conn


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Return a temp DB path (file does not need to exist yet)."""
    return tmp_path / "test_cache.db"


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication for QThread tests."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestSchema:
    def test_schema_creates_cleanly(self, tmp_path: Path) -> None:
        """init_db() must create all tables without error on a fresh DB."""
        from saebooks_desktop.cache.db import get_connection, init_db

        conn = get_connection(db_path=tmp_path / "fresh.db")
        init_db(conn)

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "entity_cache" in tables
        assert "outbox" in tables
        assert "sync_cursor" in tables
        assert "conflicts" in tables
        conn.close()

    def test_schema_is_idempotent(self, tmp_path: Path) -> None:
        """init_db() called twice must not raise."""
        from saebooks_desktop.cache.db import get_connection, init_db

        conn = get_connection(db_path=tmp_path / "idem.db")
        init_db(conn)
        # Second call should be a no-op (IF NOT EXISTS).
        init_db(conn)
        conn.close()

    def test_sync_cursor_singleton_exists(self, db: sqlite3.Connection) -> None:
        """Singleton cursor row with id=1 must exist after init_db."""
        row = db.execute(
            "SELECT change_log_cursor FROM sync_cursor WHERE id = 1"
        ).fetchone()
        assert row is not None
        assert row[0] == 0

    def test_cursor_constraint_rejects_non_one(self, db: sqlite3.Connection) -> None:
        """sync_cursor CHECK(id=1) must reject any other id."""
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO sync_cursor (id, change_log_cursor) VALUES (2, 0)"
            )


# ---------------------------------------------------------------------------
# Outbox tests
# ---------------------------------------------------------------------------


class TestOutboxEnqueue:
    def test_enqueue_inserts_row(self, db_path: Path) -> None:
        """enqueue() must add one row to the outbox."""
        from saebooks_desktop.cache.outbox import enqueue, pending_count

        enqueue(
            method="POST",
            path="/api/v1/contacts",
            body={"name": "Alice"},
            idempotency_key="key-001",
            db_path=db_path,
        )
        assert pending_count(db_path=db_path) == 1

    def test_enqueue_duplicate_ignored(self, db_path: Path) -> None:
        """Second enqueue with the same idempotency_key must not create a duplicate."""
        from saebooks_desktop.cache.outbox import enqueue, pending_count

        enqueue("POST", "/api/v1/contacts", {}, "key-dup", db_path=db_path)
        enqueue("POST", "/api/v1/contacts", {}, "key-dup", db_path=db_path)
        assert pending_count(db_path=db_path) == 1

    def test_enqueue_stores_if_match(self, db_path: Path) -> None:
        """if_match value must be persisted in the outbox row."""
        from saebooks_desktop.cache.db import get_connection, init_db
        from saebooks_desktop.cache.outbox import enqueue

        enqueue(
            "PATCH",
            "/api/v1/contacts/123",
            {"name": "Bob"},
            "key-patch-001",
            if_match=5,
            db_path=db_path,
        )
        conn = get_connection(db_path=db_path)
        init_db(conn)
        row = conn.execute("SELECT if_match FROM outbox WHERE idempotency_key = 'key-patch-001'").fetchone()
        assert row is not None
        assert row[0] == 5
        conn.close()


class TestOutboxDrain:
    def test_drain_success_removes_row(self, db_path: Path) -> None:
        """drain() with a successful mock api_client must delete the outbox row."""
        from saebooks_desktop.cache.outbox import drain, enqueue, pending_count

        enqueue("POST", "/api/v1/contacts", {"name": "Carol"}, "key-drain-ok", db_path=db_path)

        mock_client = MagicMock()
        mock_client.post.return_value = {"id": "new-id"}

        sent = drain(mock_client, db_path=db_path)
        assert sent == 1
        assert pending_count(db_path=db_path) == 0

    def test_drain_409_conflict_row_stays(self, db_path: Path) -> None:
        """On 409 conflict from a PATCH, the outbox row must remain with error stored."""
        from saebooks_desktop.cache.outbox import drain, enqueue, pending_count
        from saebooks_desktop.cache.db import get_connection, init_db

        enqueue("PATCH", "/api/v1/contacts/99", {"name": "Dave"}, "key-conflict", if_match=3, db_path=db_path)

        mock_client = MagicMock()
        # patch() returns (status_code, body); 409 triggers the conflict path.
        mock_client.patch.return_value = (409, {"detail": "version mismatch"})

        sent = drain(mock_client, db_path=db_path)
        assert sent == 0
        assert pending_count(db_path=db_path) == 1

        # Verify last_error and status were stored.
        conn = get_connection(db_path=db_path)
        init_db(conn)
        row = conn.execute(
            "SELECT last_error, attempts, status FROM outbox WHERE idempotency_key = 'key-conflict'"
        ).fetchone()
        assert row is not None
        assert row["attempts"] == 1
        assert row["last_error"] == "conflict"
        assert row["status"] == "conflict"
        conn.close()

    def test_drain_offline_stops_processing(self, db_path: Path) -> None:
        """ServerOfflineError during drain must stop without removing the row."""
        from saebooks_desktop.cache.outbox import drain, enqueue, pending_count
        from saebooks_desktop.services.api_client import ServerOfflineError

        enqueue("POST", "/api/v1/contacts", {"name": "Eve"}, "key-offline", db_path=db_path)

        mock_client = MagicMock()
        mock_client.post.side_effect = ServerOfflineError("connection refused")

        sent = drain(mock_client, db_path=db_path)
        assert sent == 0
        assert pending_count(db_path=db_path) == 1


# ---------------------------------------------------------------------------
# SyncEngine lifecycle tests
# ---------------------------------------------------------------------------


class TestSyncEngineLifecycle:
    def test_sync_engine_starts_and_stops(self, qapp, db_path: Path) -> None:
        """SyncEngine must start cleanly and stop on requestInterruption()."""
        from saebooks_desktop.cache.sync import SyncEngine

        mock_client = MagicMock()
        mock_client.is_reachable.return_value = False  # offline — no pull attempts

        engine = SyncEngine(mock_client, db_path=db_path, poll_online=1, poll_backoff=1)
        engine.start()

        # Let it run one tick.
        import time
        time.sleep(0.2)

        assert engine.isRunning()
        engine.requestInterruption()
        finished = engine.wait(5000)  # 5s timeout
        assert finished, "SyncEngine did not stop within timeout"

    def test_sync_engine_emits_offline_detected(self, qapp, db_path: Path) -> None:
        """SyncEngine must emit offline_detected when server is unreachable."""
        from PySide6.QtCore import Qt
        from saebooks_desktop.cache.sync import SyncEngine

        mock_client = MagicMock()
        mock_client.is_reachable.return_value = False

        engine = SyncEngine(mock_client, db_path=db_path, poll_online=1, poll_backoff=1)

        offline_fired = []
        # DirectConnection ensures the slot runs in the emitting (engine) thread
        # without needing the Qt event loop to relay the signal.
        engine.offline_detected.connect(
            lambda: offline_fired.append(True),
            Qt.ConnectionType.DirectConnection,
        )
        engine.start()

        import time
        # Give the background thread enough time to run one iteration.
        time.sleep(0.5)

        engine.requestInterruption()
        engine.wait(5000)
        assert offline_fired, "offline_detected signal was not emitted"


# ---------------------------------------------------------------------------
# Cursor advancement tests
# ---------------------------------------------------------------------------


class TestCursorAdvancement:
    def test_cursor_advances_after_pull(self, db_path: Path) -> None:
        """After a successful pull, sync_cursor must advance past the change ids."""
        from saebooks_desktop.cache.db import get_connection, init_db
        from saebooks_desktop.cache.sync import SyncEngine

        # Seed the DB.
        conn = get_connection(db_path=db_path)
        init_db(conn)

        mock_client = MagicMock()
        mock_client.is_reachable.return_value = True
        mock_client.get.return_value = {
            "items": [
                {
                    "id": 42,
                    "entity": "contact",
                    "entity_id": "abc-123",
                    "op": "create",
                    "version": 1,
                    "payload": {"name": "Frank", "email": "frank@example.com"},
                }
            ]
        }

        engine = SyncEngine(mock_client, db_path=db_path, poll_online=1, poll_backoff=1)

        # Call _pull_changes directly (not via background thread) for determinism.
        applied = engine._pull_changes(conn)
        assert applied == 1

        # Cursor must now be 42.
        row = conn.execute(
            "SELECT change_log_cursor FROM sync_cursor WHERE id = 1"
        ).fetchone()
        assert row[0] == 42

        # Row must be in entity_cache.
        cached = conn.execute(
            "SELECT data FROM entity_cache WHERE entity='contact' AND entity_id='abc-123'"
        ).fetchone()
        assert cached is not None
        data = json.loads(cached[0])
        assert data["name"] == "Frank"

        conn.close()

    def test_cursor_does_not_regress_on_empty_pull(self, db_path: Path) -> None:
        """An empty changes response must leave the cursor unchanged."""
        from saebooks_desktop.cache.db import get_connection, init_db
        from saebooks_desktop.cache.sync import SyncEngine

        conn = get_connection(db_path=db_path)
        init_db(conn)
        # Pre-set cursor to 10.
        conn.execute("UPDATE sync_cursor SET change_log_cursor = 10 WHERE id = 1")
        conn.commit()

        mock_client = MagicMock()
        mock_client.get.return_value = {"items": []}

        engine = SyncEngine(mock_client, db_path=db_path)
        applied = engine._pull_changes(conn)
        assert applied == 0

        row = conn.execute(
            "SELECT change_log_cursor FROM sync_cursor WHERE id = 1"
        ).fetchone()
        assert row[0] == 10  # unchanged
        conn.close()
