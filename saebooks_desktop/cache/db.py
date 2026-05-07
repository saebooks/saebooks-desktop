"""SQLite connection + schema initialisation for the local cache.

DB location:
  - Linux/other: ~/.local/share/SAE Books/cache.db   (XDG user data dir)
  - Windows:     %APPDATA%/SAE Books/cache.db

Uses platformdirs to resolve the correct path per platform.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from platformdirs import user_data_dir

# Application identity constants used by platformdirs.
_APP_NAME = "SAE Books"
_APP_AUTHOR = "SAE Engineering"


def _db_path() -> Path:
    """Return the platform-appropriate path for cache.db, creating dirs as needed."""
    data_dir = Path(user_data_dir(appname=_APP_NAME, appauthor=_APP_AUTHOR))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "cache.db"


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Open (or create) the SQLite cache DB and return a connection.

    Sets WAL journal mode and enables foreign key enforcement.  Callers are
    responsible for closing the connection when they're done with it.

    Args:
        db_path: Override the path — used in tests to point at a temp file.
    """
    path = db_path if db_path is not None else _db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    # WAL allows concurrent readers while a writer is active.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create all tables (idempotent — uses CREATE TABLE IF NOT EXISTS)."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS entity_cache (
            entity      TEXT NOT NULL,
            entity_id   TEXT NOT NULL,
            version     INTEGER NOT NULL,
            data        TEXT NOT NULL,   -- JSON blob
            synced_at   TEXT NOT NULL,
            PRIMARY KEY (entity, entity_id)
        );

        CREATE TABLE IF NOT EXISTS outbox (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            method           TEXT NOT NULL,
            path             TEXT NOT NULL,
            body             TEXT NOT NULL,
            idempotency_key  TEXT NOT NULL UNIQUE,
            if_match         INTEGER,
            created_at       TEXT NOT NULL,
            attempts         INTEGER NOT NULL DEFAULT 0,
            last_error       TEXT,
            status           TEXT NOT NULL DEFAULT 'pending'
        );

        CREATE TABLE IF NOT EXISTS conflicts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            entity          TEXT NOT NULL,
            entity_id       TEXT NOT NULL,
            resolved_at     TEXT,
            resolution      TEXT,
            server_payload  TEXT NOT NULL,   -- JSON
            local_payload   TEXT NOT NULL    -- JSON
        );

        CREATE TABLE IF NOT EXISTS sync_cursor (
            id                  INTEGER PRIMARY KEY CHECK (id = 1),
            change_log_cursor   INTEGER NOT NULL DEFAULT 0
        );

        -- Ensure the singleton cursor row exists.
        INSERT OR IGNORE INTO sync_cursor (id, change_log_cursor) VALUES (1, 0);
        """
    )
    conn.commit()
