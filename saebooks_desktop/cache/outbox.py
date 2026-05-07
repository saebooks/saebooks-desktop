"""Outbox queue operations.

The outbox table stores pending API operations that were made while the
server was offline (or were optimistically queued before a response was
received).  ``drain()`` replays them in FIFO order when online.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from saebooks_desktop.cache.db import get_connection, init_db
from saebooks_desktop.cache.models import OutboxRow


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def enqueue(
    method: str,
    path: str,
    body: Any,
    idempotency_key: str,
    if_match: int | None = None,
    *,
    conn: sqlite3.Connection | None = None,
    db_path: Path | None = None,
) -> None:
    """Insert a pending operation into the outbox.

    Args:
        method: HTTP method — ``"POST"``, ``"PATCH"``, ``"DELETE"``, etc.
        path: API path, e.g. ``"/api/v1/contacts"``.
        body: Request body; will be JSON-serialised if not already a string.
        idempotency_key: UUID string — unique per logical operation; ignored on
            duplicate (INSERT OR IGNORE) to make this safe to call on retry.
        if_match: Optional entity version for optimistic locking.
        conn: Existing open connection (used in tests / callers that own a conn).
        db_path: Override DB file path (used in tests).
    """
    body_str = body if isinstance(body, str) else json.dumps(body)
    own_conn = conn is None
    if own_conn:
        conn = get_connection(db_path)
        init_db(conn)
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO outbox
                (method, path, body, idempotency_key, if_match, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (method, path, body_str, idempotency_key, if_match, _now_iso()),
        )
        conn.commit()
    finally:
        if own_conn:
            conn.close()


def drain(
    api_client: Any,
    *,
    conn: sqlite3.Connection | None = None,
    db_path: Path | None = None,
    conflict_callback: Any | None = None,
) -> int:
    """Replay pending outbox rows in FIFO order.

    For each row:
    - On 2xx: delete the row from the outbox.
    - On 409 (conflict): write a row to the ``conflicts`` table, mark outbox
      row as ``status='conflict'``, call ``conflict_callback`` if provided,
      then **continue** to the next row (don't block the drain loop).
    - On other 4xx (non-retryable): increment ``attempts``, store error,
      stop processing (return early — don't blindly replay past a fatal error).
    - On network error / 5xx: increment ``attempts``, store error, stop.

    Args:
        api_client: API client with ``post`` / ``patch`` methods.
        conn: Existing open connection (used when caller owns the connection).
        db_path: Override DB file path (used in tests).
        conflict_callback: Optional callable invoked on 409 as
            ``conflict_callback(entity, entity_id, server_data, local_data)``.
            Runs synchronously in the drain loop — keep it non-blocking.

    Returns:
        Number of rows successfully replayed (deleted).
    """
    from saebooks_desktop.services.api_client import APIError, ServerOfflineError

    own_conn = conn is None
    if own_conn:
        conn = get_connection(db_path)
        init_db(conn)

    sent = 0
    try:
        rows = conn.execute(
            "SELECT * FROM outbox WHERE status = 'pending' ORDER BY id ASC"
        ).fetchall()

        for row_data in rows:
            row = OutboxRow.from_row(row_data)
            body = json.loads(row.body) if row.body else None
            extra_headers: dict[str, str] = {}
            if row.idempotency_key:
                extra_headers["X-Idempotency-Key"] = row.idempotency_key
            if row.if_match is not None:
                extra_headers["If-Match"] = str(row.if_match)

            try:
                method = row.method.upper()
                if method == "POST":
                    api_client.post(row.path, json=body, headers=extra_headers)
                elif method == "PATCH":
                    status, server_data = api_client.patch(
                        row.path, json=body, headers=extra_headers
                    )
                    if status == 409:
                        # Conflict — write to conflicts table, mark row, continue.
                        entity = _entity_from_path(row.path)
                        entity_id = _entity_id_from_path(row.path)
                        server_payload = (
                            server_data if isinstance(server_data, dict) else {}
                        )
                        local_payload = body or {}
                        conn.execute(
                            """
                            INSERT INTO conflicts
                                (entity, entity_id, server_payload, local_payload)
                            VALUES (?, ?, ?, ?)
                            """,
                            (
                                entity,
                                entity_id,
                                json.dumps(server_payload),
                                json.dumps(local_payload),
                            ),
                        )
                        conn.execute(
                            "UPDATE outbox SET attempts = attempts + 1, "
                            "last_error = 'conflict', status = 'conflict' "
                            "WHERE id = ?",
                            (row.id,),
                        )
                        conn.commit()
                        if conflict_callback is not None:
                            conflict_callback(
                                entity, entity_id, server_payload, local_payload
                            )
                        continue
                else:
                    # Generic fallback using post; callers should use POST/PATCH.
                    api_client.post(row.path, json=body, headers=extra_headers)

                # Success — remove from outbox.
                conn.execute("DELETE FROM outbox WHERE id = ?", (row.id,))
                conn.commit()
                sent += 1

            except ServerOfflineError as exc:
                conn.execute(
                    "UPDATE outbox SET attempts = attempts + 1, "
                    "last_error = ? WHERE id = ?",
                    (str(exc), row.id),
                )
                conn.commit()
                # Network error — stop draining; no point trying the rest.
                break

            except APIError as exc:
                conn.execute(
                    "UPDATE outbox SET attempts = attempts + 1, "
                    "last_error = ? WHERE id = ?",
                    (str(exc), row.id),
                )
                conn.commit()
                if exc.status_code is not None and 400 <= exc.status_code < 500:
                    # Non-retryable client error — stop.
                    break
                # 5xx — stop too; server might be recovering.
                break

    finally:
        if own_conn:
            conn.close()

    return sent


# ------------------------------------------------------------------
# Path parsing helpers
# ------------------------------------------------------------------


def _entity_from_path(path: str) -> str:
    """Extract entity name from an API path like ``/api/v1/contacts/123``.

    Returns the entity segment (e.g. ``"contacts"``) or ``"unknown"`` if
    the path doesn't match the expected pattern.
    """
    parts = [p for p in path.split("/") if p]
    # Expected shape: ["api", "v1", "<entity>", ...]
    if len(parts) >= 3 and parts[0] == "api" and parts[1].startswith("v"):
        return parts[2]
    return "unknown"


def _entity_id_from_path(path: str) -> str:
    """Extract entity id from an API path like ``/api/v1/contacts/123``.

    Returns the id segment or ``""`` if there is none.
    """
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 4:
        return parts[3]
    return ""


def pending_count(
    *,
    conn: sqlite3.Connection | None = None,
    db_path: Path | None = None,
) -> int:
    """Return the number of rows currently in the outbox."""
    own_conn = conn is None
    if own_conn:
        conn = get_connection(db_path)
        init_db(conn)
    try:
        row = conn.execute("SELECT COUNT(*) FROM outbox").fetchone()
        return row[0]
    finally:
        if own_conn:
            conn.close()
