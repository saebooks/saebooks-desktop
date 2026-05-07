"""Dataclasses for locally-cached entities and outbox rows."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CachedEntity:
    """One row from the ``entity_cache`` table."""

    entity: str
    entity_id: str
    version: int
    data: dict[str, Any]
    synced_at: str

    @classmethod
    def from_row(cls, row: Any) -> "CachedEntity":
        """Construct from a :class:`sqlite3.Row`."""
        return cls(
            entity=row["entity"],
            entity_id=row["entity_id"],
            version=row["version"],
            data=json.loads(row["data"]),
            synced_at=row["synced_at"],
        )


@dataclass
class OutboxRow:
    """One pending operation in the ``outbox`` table."""

    id: int
    method: str
    path: str
    body: str
    idempotency_key: str
    if_match: int | None
    created_at: str
    attempts: int
    last_error: str | None = field(default=None)
    status: str = field(default="pending")

    @classmethod
    def from_row(cls, row: Any) -> "OutboxRow":
        """Construct from a :class:`sqlite3.Row`."""
        # status column was added in cycle 3 — handle older DBs that lack it.
        row_keys = row.keys() if hasattr(row, "keys") else []
        status = row["status"] if "status" in row_keys else "pending"
        return cls(
            id=row["id"],
            method=row["method"],
            path=row["path"],
            body=row["body"],
            idempotency_key=row["idempotency_key"],
            if_match=row["if_match"],
            created_at=row["created_at"],
            attempts=row["attempts"],
            last_error=row["last_error"],
            status=status,
        )


@dataclass
class ConflictRow:
    """One row from the ``conflicts`` table."""

    id: int
    entity: str
    entity_id: str
    resolved_at: str | None
    resolution: str | None
    server_payload: dict[Any, Any]
    local_payload: dict[Any, Any]

    @classmethod
    def from_row(cls, row: Any) -> "ConflictRow":
        """Construct from a :class:`sqlite3.Row`."""
        return cls(
            id=row["id"],
            entity=row["entity"],
            entity_id=row["entity_id"],
            resolved_at=row["resolved_at"],
            resolution=row["resolution"],
            server_payload=json.loads(row["server_payload"]),
            local_payload=json.loads(row["local_payload"]),
        )
