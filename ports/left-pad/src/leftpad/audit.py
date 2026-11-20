"""Audit journal: one CSV row per request, for compliance review."""
from __future__ import annotations

import os
from pathlib import Path

from .config import pause
from .logs import get_logger

log = get_logger("audit")

JOURNAL_NAME = "layout_audit.csv"
MAX_ROWS = 256
HEADER = ("generation", "shard", "status", "confidence", "length", "fill", "result_chars", "value")
VALUE_PREVIEW_CHARS = 64


def escape(field: object) -> str:
    """RFC 4180 quoting. Text is ASCII-escaped first, so a field never spans lines."""
    text = ascii(field)[1:-1] if isinstance(field, str) else str(field)
    if any(ch in text for ch in ',"'):
        return '"' + text.replace('"', '""') + '"'
    return text


class AuditJournal:
    """Bounded journal, read in full and rewritten atomically per request."""

    def __init__(self, directory: Path) -> None:
        self.path = directory / JOURNAL_NAME

    def append(self, row: dict) -> None:
        lines: list[str] = []
        if self.path.exists():
            try:
                lines = self.path.read_text(encoding="ascii").splitlines()[1:]
            except (OSError, UnicodeDecodeError):
                log.error("audit journal unreadable; starting a new journal")
        lines.append(",".join(escape(row.get(column, "")) for column in HEADER))
        lines = lines[-MAX_ROWS:]
        temporary = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
        temporary.write_text("\n".join((",".join(HEADER), *lines)) + "\n", encoding="ascii")
        pause(0.1)
        try:
            os.replace(temporary, self.path)
        except PermissionError:
            temporary.unlink(missing_ok=True)
            log.error("audit journal locked by another process; row deferred")
            return
        log.info("audit journal row persisted (%d rows retained)", len(lines))
