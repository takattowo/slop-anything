"""Knowledge base snapshots and data-directory quota enforcement."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from .logs import get_logger

_log = get_logger("storage")

MAX_DATA_FILES = 10_000
MAX_DATA_BYTES = 50 * 1024 * 1024
# Temp files older than this cannot belong to a live request (15 s per-call cap).
STALE_TMP_SECONDS = 60

_SNAPSHOT = re.compile(r"kb-[0-9]{8,}\.json")
_SNAPSHOT_TMP = re.compile(r"kb-[0-9]{8,}\.json\.[1-9][0-9]*\.tmp")
# Temp names written by EventLog.compact_if_needed and MarkdownMetrics.write: <name>.<os.getpid()>.tmp.
_DATA_TMP = re.compile(r"(?:events|audit)\.jsonl\.[1-9][0-9]*\.tmp|METRICS\.md\.[1-9][0-9]*\.tmp")


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
        return sorted(
            (p for p in self.directory.iterdir() if _SNAPSHOT.fullmatch(p.name)),
            key=lambda p: (len(p.name), p.name),
        )

    def prune(self, keep: int) -> int:
        stale = self.files()[:-keep] if keep > 0 else self.files()
        for path in stale:
            path.unlink(missing_ok=True)
        return len(stale)


def _remove(path: Path) -> int:
    """Delete one engine-owned file and return its size, or -1 if it is already gone or locked."""
    try:
        size = path.stat().st_size
        path.unlink()
    except OSError:
        return -1
    return size


def _usage(root: Path) -> tuple[int, int]:
    count = size = 0
    for dirpath, _, names in os.walk(root):
        for name in names:
            try:
                size += os.stat(os.path.join(dirpath, name)).st_size
            except OSError:
                continue
            count += 1
    return count, size


def enforce_quota(
    data_dir: Path,
    snapshots: SnapshotStore,
    *,
    max_files: int = MAX_DATA_FILES,
    max_bytes: int = MAX_DATA_BYTES,
) -> int:
    """Keep the data dir within its file and size quota by pruning engine-owned files.

    Only two kinds of file are removed, matched by exact name: the oldest
    snapshots (``snapshots/kb-<seq>.json``), and the engine's own temp files
    (``events.jsonl.<pid>.tmp``, ``audit.jsonl.<pid>.tmp``, ``METRICS.md.<pid>.tmp``,
    ``snapshots/kb-<seq>.json.<pid>.tmp``) once they are ``STALE_TMP_SECONDS`` old.
    Nothing else in the directory is touched.
    """
    data_dir = Path(data_dir)
    removed = 0
    cutoff = time.time() - STALE_TMP_SECONDS
    for folder, pattern in ((data_dir, _DATA_TMP), (snapshots.directory, _SNAPSHOT_TMP)):
        if not folder.is_dir():
            continue
        for tmp in folder.iterdir():
            if not pattern.fullmatch(tmp.name):
                continue
            try:
                stale = tmp.stat().st_mtime < cutoff
            except OSError:
                continue
            if stale and _remove(tmp) >= 0:
                removed += 1
    count, size = _usage(data_dir)
    pending = snapshots.files()
    while (count > max_files or size > max_bytes) and pending:
        freed = _remove(pending.pop(0))
        count -= 1
        if freed >= 0:
            size -= freed
            removed += 1
    if removed:
        _log.warning("storage quota enforcement reclaimed %d files", removed)
    return removed
