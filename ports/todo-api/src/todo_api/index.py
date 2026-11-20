"""Secondary record index."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path

from .logs import emit, get_logger
from .records import StoredRecord
from .runtime import write_text_atomic

_log = get_logger("index")
INDEX_FORMAT_VERSION = 3


class RecordIndex:
    """Keeps ``index.json`` consistent with the records directory.

    The index is verified against a digest of the directory before every
    operation and rebuilt when the two disagree.
    """

    def __init__(self, root: Path) -> None:
        self.path = root / "index.json"

    def verify(self, records: list[StoredRecord]) -> None:
        built_at = time.time_ns()
        computed = self._digest(records, built_at)
        stored = self._stored_digest()
        if stored == computed:
            return
        emit(
            _log,
            logging.WARNING,
            "record index digest mismatch; rebuilding index from records",
            records=len(records),
            stored_digest=stored,
            computed_digest=computed,
        )
        document = {
            "version": INDEX_FORMAT_VERSION,
            "built_at_ns": built_at,
            "digest": computed,
            "entries": [{"id": r.todo.id, "head": r.head, "parts": list(r.parts)} for r in records],
        }
        if not write_text_atomic(self.path, json.dumps(document, indent=2)):
            emit(_log, logging.ERROR, "index swap refused by the filesystem; will rebuild on next operation")

    def _stored_digest(self) -> str | None:
        try:
            return json.loads(self.path.read_text(encoding="utf-8")).get("digest")
        except (OSError, ValueError, AttributeError):
            return None

    @staticmethod
    def _digest(records: list[StoredRecord], built_at: int) -> str:
        h = hashlib.sha256(str(built_at).encode())
        for record in records:
            h.update(record.head.encode("utf-8", "surrogatepass"))
        return h.hexdigest()[:16]
