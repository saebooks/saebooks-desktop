"""Sync engine — background QThread that polls the server and syncs local cache.

Lifecycle
---------
1. ``SyncEngine.start()`` — called from the main thread after the window is shown.
2. The engine's ``run()`` loop:
   a. On first run: if ``needs_bootstrap()``, call ``bootstrap_from_snapshot()``
      before entering the regular poll loop.
   b. Probe reachability.
   c. If online: drain outbox, pull ``/api/v1/changes?since=<cursor>``,
      apply to ``entity_cache``, advance cursor.
   d. Emit signals so the main window can update its status bar.
   e. Sleep for the poll interval (30s online, backs off to 120s after 3
      consecutive failures).
3. ``SyncEngine.requestInterruption()`` + ``wait()`` — clean shutdown.

Signals
-------
sync_started()              — emitted at the start of each sync attempt (and
                              at the start of bootstrap).
sync_completed(int)         — emitted after a successful sync or bootstrap; arg
                              is number of records applied.
sync_error(str)             — emitted when a sync attempt fails (error message).
offline_detected()          — emitted on the first failed reachability check.
online_detected()           — emitted when reachability is restored after an
                              offline period.
conflict_detected(str, str) — emitted when a 409 conflict is encountered during
                              outbox drain; args are (entity, entity_id).
"""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal

from saebooks_desktop.cache.db import get_connection, init_db
from saebooks_desktop.cache.outbox import drain

_POLL_ONLINE_S = 30
_POLL_BACKOFF_S = 120
_BACKOFF_THRESHOLD = 3  # failures before switching to backoff interval
_BOOTSTRAP_BATCH = 100  # entities per SQLite transaction during bootstrap


# ---------------------------------------------------------------------------
# Module-level bootstrap helpers (no Qt dependency — testable standalone)
# ---------------------------------------------------------------------------


def needs_bootstrap(conn: sqlite3.Connection) -> bool:
    """Return True if a bootstrap from the snapshot endpoint is needed.

    This is the case when the ``sync_cursor`` row does not exist or its
    ``change_log_cursor`` is 0 (fresh install or wiped DB).
    """
    row = conn.execute(
        "SELECT change_log_cursor FROM sync_cursor WHERE id = 1"
    ).fetchone()
    if row is None:
        return True
    return row["change_log_cursor"] == 0


def bootstrap_from_snapshot(
    api_client: Any,
    conn: sqlite3.Connection,
    progress_callback: Any | None = None,
) -> int:
    """Download and apply the ``/api/v1/snapshot`` NDJSON stream.

    Each line of the stream is expected to be one of:
    - An entity record: ``{"entity": "contact", "data": {...}, "version": 1}``
    - The final cursor line:   ``{"cursor": 12345}``

    Lines that are blank or cannot be parsed are silently skipped.

    Args:
        api_client: Must expose a ``get_stream(path)`` method that returns an
            iterable of text lines (the NDJSON response body).
        conn: Open SQLite connection with the schema already initialised.
        progress_callback: Optional ``callable(n_loaded: int)`` fired after
            every batch of ``_BOOTSTRAP_BATCH`` entities.

    Returns:
        Total number of entity rows upserted.
    """
    now = _now_iso()
    n_loaded = 0
    batch: list[tuple[str, str, int, str, str]] = []
    final_cursor: int = 0

    try:
        lines = api_client.get_stream("/api/v1/snapshot")
    except Exception:  # noqa: BLE001
        raise

    def _flush(batch: list[tuple[str, str, int, str, str]]) -> None:
        conn.executemany(
            """
            INSERT INTO entity_cache (entity, entity_id, version, data, synced_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(entity, entity_id) DO UPDATE SET
                version   = excluded.version,
                data      = excluded.data,
                synced_at = excluded.synced_at
            WHERE excluded.version >= entity_cache.version
            """,
            batch,
        )
        conn.commit()

    for raw_line in lines:
        line = raw_line.strip() if isinstance(raw_line, str) else ""
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            # Malformed line — skip gracefully.
            continue

        if not isinstance(obj, dict):
            continue

        if "cursor" in obj and len(obj) == 1:
            # Final cursor line.
            try:
                final_cursor = int(obj["cursor"])
            except (TypeError, ValueError):
                pass
            continue

        entity = obj.get("entity")
        data = obj.get("data")
        version = obj.get("version", 0)
        if not entity or not isinstance(data, dict):
            continue

        entity_id = str(data.get("id", ""))
        if not entity_id:
            continue

        batch.append((entity, entity_id, version, json.dumps(data), now))
        n_loaded += 1

        if len(batch) >= _BOOTSTRAP_BATCH:
            _flush(batch)
            batch.clear()
            if progress_callback is not None:
                progress_callback(n_loaded)

    # Flush remainder.
    if batch:
        _flush(batch)
        if progress_callback is not None:
            progress_callback(n_loaded)

    # Store final cursor.
    if final_cursor > 0:
        conn.execute(
            "INSERT OR REPLACE INTO sync_cursor (id, change_log_cursor) VALUES (1, ?)",
            (final_cursor,),
        )
        conn.commit()

    return n_loaded


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SyncEngine(QThread):
    """Background sync thread.

    Instantiate once, call ``start()`` when the main window is ready.
    Stop cleanly with ``requestInterruption(); wait()``.
    """

    sync_started = Signal()
    sync_completed = Signal(int)  # number of changes applied
    sync_error = Signal(str)
    offline_detected = Signal()
    online_detected = Signal()
    conflict_detected = Signal(str, str)  # (entity, entity_id)

    def __init__(
        self,
        api_client: Any,
        *,
        db_path: Path | None = None,
        poll_online: int = _POLL_ONLINE_S,
        poll_backoff: int = _POLL_BACKOFF_S,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._api_client = api_client
        self._db_path = db_path
        self._poll_online = poll_online
        self._poll_backoff = poll_backoff

        self._was_offline = False
        self._consecutive_failures = 0

    # ------------------------------------------------------------------
    # QThread.run — the background loop
    # ------------------------------------------------------------------

    def run(self) -> None:  # noqa: C901 (complexity)
        conn = get_connection(self._db_path)
        init_db(conn)
        try:
            # --- Bootstrap on fresh install ---
            if needs_bootstrap(conn):
                self.sync_started.emit()
                try:
                    n = bootstrap_from_snapshot(self._api_client, conn)
                    self.sync_completed.emit(n)
                except Exception as exc:  # noqa: BLE001
                    self.sync_error.emit(f"Bootstrap failed: {exc}")

            while not self.isInterruptionRequested():
                self.sync_started.emit()
                try:
                    online = self._api_client.is_reachable()
                except Exception:  # noqa: BLE001
                    online = False

                if not online:
                    if not self._was_offline:
                        self._was_offline = True
                        self.offline_detected.emit()
                    self._consecutive_failures += 1
                    self._interruptible_sleep(self._current_interval())
                    continue

                # Back online after offline?
                if self._was_offline:
                    self._was_offline = False
                    self.online_detected.emit()

                try:
                    # 1. Drain outbox first (our writes have priority).
                    def _conflict_cb(
                        entity: str, entity_id: str, _sv: Any, _lv: Any
                    ) -> None:
                        self.conflict_detected.emit(entity, entity_id)

                    drain(self._api_client, conn=conn, conflict_callback=_conflict_cb)

                    # 2. Pull changes from server.
                    changes_applied = self._pull_changes(conn)

                    self._consecutive_failures = 0
                    self.sync_completed.emit(changes_applied)

                except Exception as exc:  # noqa: BLE001
                    self._consecutive_failures += 1
                    self.sync_error.emit(str(exc))

                self._interruptible_sleep(self._current_interval())
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _current_interval(self) -> int:
        if self._consecutive_failures >= _BACKOFF_THRESHOLD:
            return self._poll_backoff
        return self._poll_online

    def _interruptible_sleep(self, seconds: int) -> None:
        """Sleep in 1-second chunks, checking for interruption each tick."""
        for _ in range(seconds):
            if self.isInterruptionRequested():
                break
            time.sleep(1)

    def _pull_changes(self, conn: sqlite3.Connection) -> int:
        """Pull ``/api/v1/changes`` from server and apply to entity_cache.

        Returns the number of change events applied.
        """
        # Read current cursor.
        cursor_row = conn.execute(
            "SELECT change_log_cursor FROM sync_cursor WHERE id = 1"
        ).fetchone()
        cursor = cursor_row["change_log_cursor"] if cursor_row else 0

        try:
            data = self._api_client.get(
                "/api/v1/changes",
                params={"since": cursor, "limit": 500},
            )
        except Exception:  # noqa: BLE001
            raise

        items = data.get("items", []) if isinstance(data, dict) else []
        if not items:
            return 0

        now = _now_iso()
        new_cursor = cursor
        applied = 0

        for change in items:
            entity = change.get("entity", "")
            entity_id = str(change.get("entity_id", ""))
            version = change.get("version", 0)
            op = change.get("op", "")
            payload = change.get("payload", {})
            change_id = change.get("id", cursor)

            if op == "archive":
                conn.execute(
                    "DELETE FROM entity_cache WHERE entity = ? AND entity_id = ?",
                    (entity, entity_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO entity_cache (entity, entity_id, version, data, synced_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(entity, entity_id) DO UPDATE SET
                        version  = excluded.version,
                        data     = excluded.data,
                        synced_at = excluded.synced_at
                    WHERE excluded.version > entity_cache.version
                    """,
                    (entity, entity_id, version, json.dumps(payload), now),
                )

            if change_id > new_cursor:
                new_cursor = change_id
            applied += 1

        # Advance cursor.
        conn.execute(
            "UPDATE sync_cursor SET change_log_cursor = ? WHERE id = 1",
            (new_cursor,),
        )
        conn.commit()
        return applied
