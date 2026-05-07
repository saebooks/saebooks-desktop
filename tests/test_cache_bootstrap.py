"""Tests for bootstrap snapshot logic (needs_bootstrap + bootstrap_from_snapshot).

All tests use temporary SQLite files (tmp_path) and mock the api_client.
No live server or Qt required for these tests.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    from saebooks_desktop.cache.db import get_connection, init_db

    conn = get_connection(db_path=tmp_path / "test_bootstrap.db")
    init_db(conn)
    return conn


# ---------------------------------------------------------------------------
# needs_bootstrap tests
# ---------------------------------------------------------------------------


class TestNeedsBootstrap:
    def test_returns_true_on_fresh_db(self, db: sqlite3.Connection) -> None:
        """needs_bootstrap() must return True right after init_db (cursor == 0)."""
        from saebooks_desktop.cache.sync import needs_bootstrap

        assert needs_bootstrap(db) is True

    def test_returns_false_after_cursor_set(self, db: sqlite3.Connection) -> None:
        """needs_bootstrap() must return False once a non-zero cursor is stored."""
        from saebooks_desktop.cache.sync import needs_bootstrap

        db.execute(
            "UPDATE sync_cursor SET change_log_cursor = 42 WHERE id = 1"
        )
        db.commit()
        assert needs_bootstrap(db) is False

    def test_returns_true_when_cursor_reset_to_zero(
        self, db: sqlite3.Connection
    ) -> None:
        """needs_bootstrap() must return True if cursor is reset to 0."""
        from saebooks_desktop.cache.sync import needs_bootstrap

        db.execute("UPDATE sync_cursor SET change_log_cursor = 99 WHERE id = 1")
        db.commit()
        db.execute("UPDATE sync_cursor SET change_log_cursor = 0 WHERE id = 1")
        db.commit()
        assert needs_bootstrap(db) is True


# ---------------------------------------------------------------------------
# bootstrap_from_snapshot tests
# ---------------------------------------------------------------------------


def _make_ndjson_stream(*lines: str):
    """Return a list of NDJSON lines (simulates the iterable from get_stream)."""
    return list(lines)


class TestBootstrapFromSnapshot:
    def test_upserts_entities_and_sets_cursor(
        self, db: sqlite3.Connection
    ) -> None:
        """bootstrap_from_snapshot must upsert entity rows and advance cursor."""
        from saebooks_desktop.cache.sync import bootstrap_from_snapshot, needs_bootstrap

        lines = [
            json.dumps({"entity": "contact", "data": {"id": "c-1", "name": "Alice"}, "version": 1}),
            json.dumps({"entity": "contact", "data": {"id": "c-2", "name": "Bob"}, "version": 1}),
            json.dumps({"entity": "account", "data": {"id": "a-1", "name": "Cash"}, "version": 2}),
            json.dumps({"cursor": 99}),
        ]

        mock_client = MagicMock()
        mock_client.get_stream.return_value = iter(lines)

        n = bootstrap_from_snapshot(mock_client, db)

        assert n == 3
        # Cursor must be 99.
        assert needs_bootstrap(db) is False
        row = db.execute(
            "SELECT change_log_cursor FROM sync_cursor WHERE id = 1"
        ).fetchone()
        assert row[0] == 99

        # Entities in cache.
        cached_ids = {
            r["entity_id"]
            for r in db.execute("SELECT entity_id FROM entity_cache").fetchall()
        }
        assert cached_ids == {"c-1", "c-2", "a-1"}

    def test_progress_callback_fires_per_batch(
        self, db: sqlite3.Connection
    ) -> None:
        """progress_callback must be called after every batch of 100 entities."""
        from saebooks_desktop.cache.sync import bootstrap_from_snapshot, _BOOTSTRAP_BATCH

        # 250 entities → 3 callbacks (100, 200, 250).
        lines = [
            json.dumps({"entity": "contact", "data": {"id": f"c-{i}", "name": f"X{i}"}, "version": 1})
            for i in range(250)
        ]
        lines.append(json.dumps({"cursor": 250}))

        mock_client = MagicMock()
        mock_client.get_stream.return_value = iter(lines)

        calls: list[int] = []
        bootstrap_from_snapshot(mock_client, db, progress_callback=calls.append)

        # Should have been called after batch 1 (100), batch 2 (200), remainder (250).
        assert len(calls) == 3
        assert calls[0] == 100
        assert calls[1] == 200
        assert calls[2] == 250

    def test_malformed_ndjson_lines_skipped(
        self, db: sqlite3.Connection
    ) -> None:
        """Malformed NDJSON lines must be skipped without crashing."""
        from saebooks_desktop.cache.sync import bootstrap_from_snapshot

        lines = [
            "not valid json {{{",
            "",
            json.dumps({"entity": "contact", "data": {"id": "c-ok", "name": "Good"}, "version": 1}),
            '{"broken":',
            json.dumps({"cursor": 5}),
        ]

        mock_client = MagicMock()
        mock_client.get_stream.return_value = iter(lines)

        n = bootstrap_from_snapshot(mock_client, db)
        assert n == 1  # only the good line

        cached = db.execute(
            "SELECT entity_id FROM entity_cache"
        ).fetchall()
        assert len(cached) == 1
        assert cached[0]["entity_id"] == "c-ok"

    def test_empty_stream_leaves_cursor_zero(
        self, db: sqlite3.Connection
    ) -> None:
        """An empty stream (no cursor line) must leave cursor at 0."""
        from saebooks_desktop.cache.sync import bootstrap_from_snapshot, needs_bootstrap

        mock_client = MagicMock()
        mock_client.get_stream.return_value = iter([])

        n = bootstrap_from_snapshot(mock_client, db)
        assert n == 0
        assert needs_bootstrap(db) is True  # cursor still 0

    def test_stream_without_cursor_line_leaves_cursor_zero(
        self, db: sqlite3.Connection
    ) -> None:
        """A stream with entity rows but no final cursor line must leave cursor at 0."""
        from saebooks_desktop.cache.sync import bootstrap_from_snapshot, needs_bootstrap

        lines = [
            json.dumps({"entity": "contact", "data": {"id": "c-1", "name": "Alice"}, "version": 1}),
        ]
        mock_client = MagicMock()
        mock_client.get_stream.return_value = iter(lines)

        n = bootstrap_from_snapshot(mock_client, db)
        assert n == 1
        # No cursor line → cursor stays 0, bootstrap will run again next time.
        assert needs_bootstrap(db) is True

    def test_entities_missing_id_field_skipped(
        self, db: sqlite3.Connection
    ) -> None:
        """Entity lines without an 'id' field in data must be skipped gracefully."""
        from saebooks_desktop.cache.sync import bootstrap_from_snapshot

        lines = [
            json.dumps({"entity": "contact", "data": {"name": "No ID Here"}, "version": 1}),
            json.dumps({"entity": "contact", "data": {"id": "c-good", "name": "Has ID"}, "version": 1}),
            json.dumps({"cursor": 10}),
        ]
        mock_client = MagicMock()
        mock_client.get_stream.return_value = iter(lines)

        n = bootstrap_from_snapshot(mock_client, db)
        assert n == 1  # only the one with an id

    def test_skipped_bootstrap_when_cursor_nonzero(
        self, db: sqlite3.Connection
    ) -> None:
        """needs_bootstrap() returning False means bootstrap_from_snapshot should
        NOT be called — test this by verifying the guard in SyncEngine.run()
        indirectly through needs_bootstrap behaviour."""
        from saebooks_desktop.cache.sync import needs_bootstrap

        db.execute("UPDATE sync_cursor SET change_log_cursor = 50 WHERE id = 1")
        db.commit()
        # SyncEngine.run() checks needs_bootstrap(conn) before calling bootstrap.
        # Here we just confirm needs_bootstrap returns False — the integration test
        # for run() skipping bootstrap is covered by the lifecycle tests in test_cache.py.
        assert needs_bootstrap(db) is False
