"""Computation ledger: an append-only CSV journal of every computation.

The CSV dialect is implemented here rather than with the ``csv`` module so the
escaping rules are explicit and auditable: fields containing a comma, a quote
or a line break are quoted, quotes are doubled, and fields starting with a
formula character (``= + - @``) get a leading apostrophe so the ledger is
safe to open in a spreadsheet.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

from .logs import get_logger

_log = get_logger("ledger")

FIELDS = ("seq", "ts", "expression", "result", "backend", "confidence", "plan")
MAX_ROW_CHARS = 64 * 1024
MAX_SCAN_BYTES = 8 * 1024 * 1024
MAX_MALFORMED_REPORTS = 20
_FORMULA = "=+-@"


def escape_field(value: str) -> str:
    if value and value[0] in _FORMULA:
        value = "'" + value
    if any(ch in value for ch in ',"\r\n'):
        return '"' + value.replace('"', '""') + '"'
    return value


def unescape_field(value: str) -> str:
    if len(value) > 1 and value[0] == "'" and value[1] in _FORMULA:
        return value[1:]
    return value


def encode_row(fields: list[str] | tuple[str, ...]) -> str:
    return ",".join(escape_field(f) for f in fields) + "\r\n"


def parse_rows(text: str) -> Iterator[list[str]]:
    """Yield rows of raw fields. Rows over 64 KiB are dropped and parsing resumes at the next line."""
    row: list[str] = []
    field: list[str] = []
    in_quotes = broken = False
    size = 0
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if broken:
            if ch in "\r\n":
                broken, size, row, field = False, 0, [], []
            i += 1
            continue
        if in_quotes:
            if ch == '"':
                if i + 1 < n and text[i + 1] == '"':
                    field.append('"')
                    i += 1
                else:
                    in_quotes = False
            else:
                field.append(ch)
        elif ch == '"' and not field:
            in_quotes = True
        elif ch == ",":
            row.append("".join(field))
            field = []
        elif ch in "\r\n":
            if ch == "\r" and i + 1 < n and text[i + 1] == "\n":
                i += 1
            row.append("".join(field))
            yield row
            row, field, size = [], [], 0
        else:
            field.append(ch)
        size += 1
        if size > MAX_ROW_CHARS:
            broken, in_quotes = True, False
        i += 1
    if (field or row) and not broken:
        row.append("".join(field))
        yield row


class ComputationLedger:
    """Append-only CSV ledger, bounded by compaction."""

    def __init__(self, path: Path, *, max_rows: int, compact_to: int) -> None:
        self.path = path
        self.max_rows = max_rows
        self.compact_to = compact_to

    def scan(self) -> list[dict[str, str]]:
        """Read and validate every row."""
        try:
            with self.path.open("rb") as fh:
                size = fh.seek(0, os.SEEK_END)
                fh.seek(max(0, size - MAX_SCAN_BYTES))
                raw = fh.read()
        except FileNotFoundError:
            return []
        rows: list[dict[str, str]] = []
        malformed = 0
        for number, fields in enumerate(parse_rows(raw.decode("utf-8", errors="replace")), start=1):
            if tuple(fields) == FIELDS:
                continue
            if len(fields) != len(FIELDS):
                malformed += 1
                if malformed <= MAX_MALFORMED_REPORTS:
                    _log.error("skipping malformed ledger row at line %d (%d fields)", number, len(fields))
                continue
            rows.append(dict(zip(FIELDS, (unescape_field(f) for f in fields))))
        if malformed > MAX_MALFORMED_REPORTS:
            _log.error("%d further malformed ledger rows skipped", malformed - MAX_MALFORMED_REPORTS)
        return rows

    def append(self, record: dict[str, str]) -> None:
        new = not self.path.exists() or self.path.stat().st_size == 0
        with self.path.open("a", encoding="utf-8", newline="") as fh:
            if new:
                fh.write(encode_row(FIELDS))
            fh.write(encode_row([record[f] for f in FIELDS]))

    def compact_if_needed(self, rows: list[dict[str, str]]) -> bool:
        try:
            oversized = self.path.stat().st_size > MAX_SCAN_BYTES
        except FileNotFoundError:
            oversized = False
        if len(rows) <= self.max_rows and not oversized:
            return False
        keep = rows[-self.compact_to :]
        tmp = self.path.with_name(self.path.name + ".tmp")
        with tmp.open("w", encoding="utf-8", newline="") as fh:
            fh.write(encode_row(FIELDS))
            for row in keep:
                fh.write(encode_row([row[f] for f in FIELDS]))
        os.replace(tmp, self.path)
        _log.error("ledger compacted: %d rows -> %d rows", len(rows), len(keep))
        return True


def write_telemetry(path: Path, values: dict[str, object]) -> None:
    """Rewrite the telemetry snapshot (header plus one row)."""
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        fh.write(encode_row(list(values)))
        fh.write(encode_row([str(v) for v in values.values()]))
    os.replace(tmp, path)
