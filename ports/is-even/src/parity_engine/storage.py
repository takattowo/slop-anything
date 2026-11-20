"""Knowledge base snapshots and data-directory quota enforcement."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .logs import get_logger

_log = get_logger("storage")

MAX_DATA_FILES = 10_000
MAX_DATA_BYTES = 50 * 1024 * 1024


class SnapshotStore:
    """Point-in-time knowledge base snapshots, newest ``retain`` kept."""

    def __init__(self, directory: Path, *, retain: int) -> None:
        self.directory = Path(directory)
        self.retain = retain

    def write(self, seq: int, payload: dict) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.directory / f"kb-{seq:08d}.json"
        tmp = target.with_name(f"{target.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
        try:
            os.replace(tmp, target)
        except PermissionError:
            tmp.unlink(missing_ok=True)
            _log.error("snapshot %s is held open by another process; snapshot skipped", target.name)
        self.prune(self.retain)
        return target

    def files(self) -> list[Path]:
        if not self.directory.is_dir():
            return []
        return sorted(self.directory.glob("kb-*.json"))

    def prune(self, keep: int) -> int:
        stale = self.files()[:-keep] if keep > 0 else self.files()
        for path in stale:
            path.unlink(missing_ok=True)
        return len(stale)


def enforce_quota(
    data_dir: Path,
    snapshots: SnapshotStore,
    *,
    max_files: int = MAX_DATA_FILES,
    max_bytes: int = MAX_DATA_BYTES,
) -> int:
    """Keep the data dir within its file and size quota by pruning engine-owned files.

    Only snapshots and leftover ``*.tmp`` files written by the engine are
    removed; nothing else in the directory is touched.
    """
    removed = 0
    for tmp in Path(data_dir).glob("*.tmp"):
        tmp.unlink(missing_ok=True)
        removed += 1
    files = [p for p in Path(data_dir).rglob("*") if p.is_file()]
    count, size = len(files), sum(p.stat().st_size for p in files)
    pending = snapshots.files()
    while (count > max_files or size > max_bytes) and pending:
        victim = pending.pop(0)
        size -= victim.stat().st_size
        victim.unlink(missing_ok=True)
        count -= 1
        removed += 1
    if removed:
        _log.warning("storage quota enforcement reclaimed %d files", removed)
    return removed
