"""Data directory compaction: keeps the engine's own files within the storage caps."""
from __future__ import annotations

import re
import stat
import time
from pathlib import Path

from .audit import JOURNAL_NAME
from .logs import get_logger
from .registry import REGISTRY_FILENAME, REPLICA_FILENAMES
from .telemetry import ARCHIVE_NAME

log = get_logger("janitor")

MAX_DATA_BYTES = 50 * 1024 * 1024
MAX_DATA_FILES = 10_000
COMPACT_BYTES = 40 * 1024 * 1024
COMPACT_FILES = 9_000
STALE_AFTER_SECONDS = 60.0
"""An interrupted write leaves a temporary file; one this old has no writer left."""

OWN_FILENAMES = frozenset((REGISTRY_FILENAME, *REPLICA_FILENAMES, ARCHIVE_NAME, JOURNAL_NAME))
"""Every file the engine writes, by exact name, at the top level of its data folder."""
OWN_TEMPORARY = re.compile("(?:" + "|".join(re.escape(name) for name in sorted(OWN_FILENAMES)) + r")\.[0-9]+\.tmp")
"""The engine's own temporary files: ``<own file>.<pid>.tmp``."""


def _own_files(directory: Path) -> list[tuple[Path, float, int, bool]]:
    """One stat snapshot per own file: path, mtime, size, temporary. Files gone mid-scan are skipped."""
    found = []
    try:
        entries = list(directory.iterdir())
    except OSError:
        return found
    for path in entries:
        temporary = OWN_TEMPORARY.fullmatch(path.name) is not None
        if not temporary and path.name not in OWN_FILENAMES:
            continue
        try:
            info = path.stat()
        except OSError:
            continue
        if stat.S_ISREG(info.st_mode):
            found.append((path, info.st_mtime, info.st_size, temporary))
    return found


class DataDirJanitor:
    """Prunes only files the engine itself writes, never anything else in the directory."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def compact(self) -> None:
        now = time.time()
        removed = 0
        files = []
        for path, mtime, size, temporary in _own_files(self.directory):
            if temporary and now - mtime >= STALE_AFTER_SECONDS:
                try:
                    path.unlink()
                    removed += 1
                except OSError:
                    pass
                continue
            files.append((mtime, path, size))
        files.sort(key=lambda item: item[0])
        total = sum(size for _, _, size in files)
        while files and (len(files) > COMPACT_FILES or total > COMPACT_BYTES):
            _, oldest, size = files.pop(0)
            try:
                oldest.unlink()
                removed += 1
            except OSError:
                pass
            total -= size
        log.info("data directory compaction completed: %d files reclaimed, %d bytes retained", removed, total)
