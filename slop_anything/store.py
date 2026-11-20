"""Transactional state persistence on SQLite.

The whole harness state is one JSON document kept in a single row. Every
write loads the document, applies the change, writes the full document back
and reads it again to confirm the revision.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Callable, TypeVar

from slop_anything.observability import get_logger
from slop_anything.settings import state_dir

T = TypeVar("T")
STATE_FILE = "state.sqlite3"
SCHEMA = (
    "CREATE TABLE IF NOT EXISTS harness_state ("
    "id INTEGER PRIMARY KEY CHECK (id = 1), "
    "revision INTEGER NOT NULL, "
    "document TEXT NOT NULL)"
)
EMPTY_DOCUMENT: dict[str, Any] = {"recordings": {}, "telemetry": {}, "negative_lookups": [], "calls": 0}
_log = get_logger("store")


def _fresh(document: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(EMPTY_DOCUMENT))
    merged.update(json.loads(json.dumps(document)))
    return merged


class StateStore:
    """Unit of Work over the harness state document."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else state_dir() / STATE_FILE
        self._rebuild_index()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute(SCHEMA)
        return connection

    def _rebuild_index(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("PRAGMA integrity_check").fetchall()
            connection.execute("REINDEX")
        _log.error("detected corrupted state index in %s, rebuilding", self.path.name)

    def _read(self, connection: sqlite3.Connection) -> tuple[int, dict[str, Any]]:
        row = connection.execute("SELECT revision, document FROM harness_state WHERE id = 1").fetchone()
        if row is None:
            return 0, _fresh({})
        return int(row[0]), _fresh(json.loads(row[1]))

    def load(self) -> dict[str, Any]:
        """Returns a private copy of the current document."""
        with closing(self._connect()) as connection:
            return self._read(connection)[1]

    def revision(self) -> int:
        with closing(self._connect()) as connection:
            return self._read(connection)[0]

    def mutate(self, change: Callable[[dict[str, Any]], T]) -> T:
        """Applies ``change`` to the document in place and rewrites the whole row atomically."""
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                revision, document = self._read(connection)
                result = change(document)
                connection.execute(
                    "INSERT OR REPLACE INTO harness_state (id, revision, document) VALUES (1, ?, ?)",
                    (revision + 1, json.dumps(document, sort_keys=True, ensure_ascii=False)),
                )
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
            confirmed, _ = self._read(connection)
        if confirmed != revision + 1:
            _log.error("state revision drifted: expected %d, found %d", revision + 1, confirmed)
        return result
