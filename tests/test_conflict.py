"""Tests for conflict detection in outbox drain + ConflictDialog.

All tests are offscreen-safe and use temporary SQLite files (tmp_path).
No live API server is required.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Force offscreen Qt platform before any PySide6 import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    """Open a fresh temp DB with full schema."""
    from saebooks_desktop.cache.db import get_connection, init_db

    conn = get_connection(db_path=tmp_path / "test_conflict.db")
    init_db(conn)
    return conn


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_conflict.db"


# ---------------------------------------------------------------------------
# Outbox drain — 409 conflict path
# ---------------------------------------------------------------------------


class TestOutboxDrainConflict:
    def test_409_writes_conflict_row(self, db_path: Path) -> None:
        """A 409 from PATCH must write a row to the conflicts table."""
        from saebooks_desktop.cache.outbox import drain, enqueue
        from saebooks_desktop.cache.db import get_connection, init_db

        enqueue(
            "PATCH",
            "/api/v1/contacts/abc-001",
            {"name": "Alice Edited"},
            "key-conf-01",
            if_match=2,
            db_path=db_path,
        )

        server_response = {"id": "abc-001", "name": "Alice Server", "version": 3}
        mock_client = MagicMock()
        mock_client.patch.return_value = (409, server_response)

        drain(mock_client, db_path=db_path)

        conn = get_connection(db_path=db_path)
        init_db(conn)
        rows = conn.execute("SELECT * FROM conflicts").fetchall()
        assert len(rows) == 1
        row = rows[0]
        assert row["entity"] == "contacts"
        assert row["entity_id"] == "abc-001"
        server_payload = json.loads(row["server_payload"])
        assert server_payload["name"] == "Alice Server"
        local_payload = json.loads(row["local_payload"])
        assert local_payload["name"] == "Alice Edited"
        conn.close()

    def test_409_marks_outbox_row_conflict(self, db_path: Path) -> None:
        """A 409 must set the outbox row's status to 'conflict'."""
        from saebooks_desktop.cache.outbox import drain, enqueue
        from saebooks_desktop.cache.db import get_connection, init_db

        enqueue(
            "PATCH",
            "/api/v1/contacts/abc-002",
            {"name": "Bob"},
            "key-conf-02",
            if_match=1,
            db_path=db_path,
        )

        mock_client = MagicMock()
        mock_client.patch.return_value = (409, {"name": "Bob Server"})

        drain(mock_client, db_path=db_path)

        conn = get_connection(db_path=db_path)
        init_db(conn)
        row = conn.execute(
            "SELECT status, attempts FROM outbox WHERE idempotency_key = 'key-conf-02'"
        ).fetchone()
        assert row is not None
        assert row["status"] == "conflict"
        assert row["attempts"] == 1
        conn.close()

    def test_409_drain_continues_to_next_item(self, db_path: Path) -> None:
        """After a 409 conflict, drain must continue processing subsequent rows."""
        from saebooks_desktop.cache.outbox import drain, enqueue, pending_count
        from saebooks_desktop.cache.db import get_connection, init_db

        # Row 1 — will 409
        enqueue(
            "PATCH",
            "/api/v1/contacts/abc-003",
            {"name": "Conflict"},
            "key-conf-03a",
            if_match=1,
            db_path=db_path,
        )
        # Row 2 — will succeed
        enqueue(
            "POST",
            "/api/v1/contacts",
            {"name": "Success"},
            "key-conf-03b",
            db_path=db_path,
        )

        mock_client = MagicMock()
        mock_client.patch.return_value = (409, {})
        mock_client.post.return_value = {"id": "new-id"}

        sent = drain(mock_client, db_path=db_path)
        # Row 2 should have been sent successfully.
        assert sent == 1

        conn = get_connection(db_path=db_path)
        init_db(conn)
        # Row 1 (conflict) stays; row 2 was removed.
        remaining = conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
        assert remaining == 1
        conflict_row = conn.execute(
            "SELECT status FROM outbox WHERE idempotency_key = 'key-conf-03a'"
        ).fetchone()
        assert conflict_row["status"] == "conflict"
        conn.close()

    def test_409_calls_conflict_callback(self, db_path: Path) -> None:
        """A 409 must invoke the conflict_callback with entity + entity_id."""
        from saebooks_desktop.cache.outbox import drain, enqueue

        enqueue(
            "PATCH",
            "/api/v1/invoices/inv-999",
            {"total": 500},
            "key-conf-04",
            if_match=1,
            db_path=db_path,
        )

        mock_client = MagicMock()
        mock_client.patch.return_value = (409, {"total": 600})

        callback_calls: list[tuple[str, str, dict, dict]] = []

        def _cb(entity, entity_id, server_data, local_data):
            callback_calls.append((entity, entity_id, server_data, local_data))

        drain(mock_client, db_path=db_path, conflict_callback=_cb)

        assert len(callback_calls) == 1
        entity, entity_id, server_data, local_data = callback_calls[0]
        assert entity == "invoices"
        assert entity_id == "inv-999"
        assert server_data == {"total": 600}
        assert local_data == {"total": 500}


# ---------------------------------------------------------------------------
# ConflictDialog UI tests (offscreen)
# ---------------------------------------------------------------------------


class TestConflictDialog:
    def test_conflict_dialog_instantiates(self, qapp) -> None:
        """ConflictDialog must construct without crash."""
        from saebooks_desktop.views.conflict_dialog import ConflictDialog

        dlg = ConflictDialog(
            entity="contact",
            entity_id="abc-001",
            server_data={"name": "Server Alice", "email": "server@example.com"},
            local_data={"name": "My Alice", "email": "local@example.com"},
        )
        assert dlg is not None
        assert dlg.windowTitle() == "Sync Conflict"

    def test_keep_server_sets_resolution_and_accepts(self, qapp) -> None:
        """Clicking Keep Server Version must set resolution to 'keep_server' and accept."""
        from saebooks_desktop.views.conflict_dialog import (
            ConflictDialog,
            RESOLUTION_KEEP_SERVER,
        )
        from PySide6.QtWidgets import QDialog

        dlg = ConflictDialog(
            entity="contact",
            entity_id="abc-002",
            server_data={"name": "Server"},
            local_data={"name": "Local"},
        )
        # Simulate clicking the button directly — no event loop needed.
        dlg._keep_server_btn.click()

        assert dlg.resolution == RESOLUTION_KEEP_SERVER
        assert dlg.result() == QDialog.DialogCode.Accepted

    def test_keep_local_sets_resolution_and_accepts(self, qapp) -> None:
        """Clicking Keep My Version must set resolution to 'keep_local' and accept."""
        from saebooks_desktop.views.conflict_dialog import (
            ConflictDialog,
            RESOLUTION_KEEP_LOCAL,
        )
        from PySide6.QtWidgets import QDialog

        dlg = ConflictDialog(
            entity="contact",
            entity_id="abc-003",
            server_data={"name": "Server"},
            local_data={"name": "Local"},
        )
        dlg._keep_local_btn.click()

        assert dlg.resolution == RESOLUTION_KEEP_LOCAL
        assert dlg.result() == QDialog.DialogCode.Accepted

    def test_cancel_rejects_dialog(self, qapp) -> None:
        """Clicking Cancel must reject the dialog with None resolution."""
        from saebooks_desktop.views.conflict_dialog import ConflictDialog
        from PySide6.QtWidgets import QDialog

        dlg = ConflictDialog(
            entity="contact",
            entity_id="abc-004",
            server_data={"name": "Server"},
            local_data={"name": "Local"},
        )
        dlg._cancel_btn.click()

        assert dlg.resolution is None
        assert dlg.result() == QDialog.DialogCode.Rejected

    def test_conflict_dialog_with_json_string_inputs(self, qapp) -> None:
        """ConflictDialog must accept JSON strings as well as dicts."""
        from saebooks_desktop.views.conflict_dialog import ConflictDialog

        dlg = ConflictDialog(
            entity="invoice",
            entity_id="inv-001",
            server_data='{"total": 100}',
            local_data='{"total": 200}',
        )
        assert dlg is not None
        # Both panes should contain parseable JSON.
        server_text = dlg._server_pane.toPlainText()
        local_text = dlg._local_pane.toPlainText()
        assert "100" in server_text
        assert "200" in local_text


# ---------------------------------------------------------------------------
# BootstrapProgressDialog UI tests (offscreen)
# ---------------------------------------------------------------------------


class TestBootstrapProgressDialog:
    def test_dialog_instantiates(self, qapp) -> None:
        """BootstrapProgressDialog must construct without crash."""
        from saebooks_desktop.views.bootstrap_progress import BootstrapProgressDialog

        dlg = BootstrapProgressDialog()
        assert dlg is not None
        assert "SAE Books" in dlg.windowTitle()

    def test_on_progress_updates_label(self, qapp) -> None:
        """on_progress(n) must update the count label text."""
        from saebooks_desktop.views.bootstrap_progress import BootstrapProgressDialog

        dlg = BootstrapProgressDialog()
        dlg.on_progress(250)
        assert "250" in dlg._count_label.text()

    def test_on_sync_completed_accepts_dialog(self, qapp) -> None:
        """on_sync_completed must close the dialog with Accepted result."""
        from saebooks_desktop.views.bootstrap_progress import BootstrapProgressDialog
        from PySide6.QtWidgets import QDialog

        dlg = BootstrapProgressDialog()
        dlg.on_sync_completed(1500)
        # Result must be Accepted after on_sync_completed.
        assert dlg.result() == QDialog.DialogCode.Accepted
        assert "1,500" in dlg._count_label.text()
