"""Data directory compaction: keeps the engine's own files within the storage caps."""
from __future__ import annotations

import time
from pathlib import Path

from .logs import get_logger

log = get_logger("janitor")

MAX_DATA_BYTES = 50 * 1024 * 1024
MAX_DATA_FILES = 10_000
COMPACT_BYTES = 40 * 1024 * 1024
COMPACT_FILES = 9_000
STALE_AFTER_SECONDS = 60.0
"""An interrupted write leaves a temporary file; one this old has no writer left."""

OWN_PATTERNS = ("_layout_registry*.py", "layout_telemetry.zip", "layout_audit.csv")
OWN_TEMPORARY_PATTERNS = ("_layout_registry*.tmp", "layout_*.tmp")


def _matches(directory: Path, patterns: tuple[str, ...]) -> list[Path]:
    found: dict[Path, None] = {}
    for pattern in patterns:
        for path in directory.glob(pattern):
            if path.is_file():
                found[path] = None
    return list(found)


class DataDirJanitor:
    """Prunes only files the engine itself writes, never anything else in the directory."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def compact(self) -> None:
        now = time.time()
        removed = 0
        temporary = _matches(self.directory, OWN_TEMPORARY_PATTERNS)
        for path in temporary:
            try:
                if now - path.stat().st_mtime >= STALE_AFTER_SECONDS:
                    path.unlink()
                    removed += 1
            except OSError:
                continue
        files = sorted(
            _matches(self.directory, OWN_TEMPORARY_PATTERNS) + _matches(self.directory, OWN_PATTERNS),
            key=lambda p: p.stat().st_mtime if p.exists() else 0.0,
        )
        sizes = {path: path.stat().st_size for path in files if path.exists()}
        total = sum(sizes.values())
        while files and (len(files) > COMPACT_FILES or total > COMPACT_BYTES):
            oldest = files.pop(0)
            try:
                oldest.unlink()
                removed += 1
            except OSError:
                pass
            total -= sizes.get(oldest, 0)
        log.info("data directory compaction completed: %d files reclaimed, %d bytes retained", removed, total)
