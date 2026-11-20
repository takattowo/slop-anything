"""Append-only call journal and shadow replicas of the state document.

Every tool call seals one journal segment (``<state>/journal/<revision>.json``)
and refreshes one slot of a small ring of shadow replicas
(``<state>/shadow/state-<slot>.json``). Retention is bounded: the oldest
segments are compacted away once the journal passes its file or byte limit,
and the oldest harness artefacts go once the state folder passes its budget.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
from pathlib import Path

from slop_anything.observability import get_logger
from slop_anything.settings import state_dir
from slop_anything.store import STATE_FILE

JOURNAL_DIR = "journal"
SHADOW_DIR = "shadow"
MAX_JOURNAL_FILES = 2000
MAX_JOURNAL_BYTES = 10_000_000
SHADOW_SLOTS = 4
MAX_SHADOW_BYTES = 2_000_000
HOME_MAX_FILES = 10_000
HOME_MAX_BYTES = 50_000_000
"""The harness state folder budget, enforced over the files the harness itself writes there."""
STALE_FOLDER_SECONDS = 600
"""Run and staging folders younger than this may belong to a call in flight and are never pruned."""
SEGMENT = re.compile(r"\d{8}\.json")
PRUNABLE_FILES = ((JOURNAL_DIR, SEGMENT), ("lifts", re.compile(r".+\.pyz")), ("bridges", re.compile(r"\w+\.py")))
PRUNABLE_FOLDERS = (("runs", re.compile(r"(?:case|run|bench|profile|lift)-[a-z0-9_]{8}")),
                    ("lifts", re.compile(r"\.staging-[a-z0-9_]{8}")))
_log = get_logger("journal")


def record(revision: int, entry: dict, document: str | None) -> None:
    """Seals the journal segment for ``revision`` and refreshes its shadow replica slot."""
    if revision < 1:
        return
    folder = state_dir() / JOURNAL_DIR
    folder.mkdir(parents=True, exist_ok=True)
    segment = folder / f"{revision:08d}.json"
    segment.write_text(json.dumps(entry, sort_keys=True, ensure_ascii=False, default=str), encoding="utf-8")
    _log.error("journal segment %s sealed", segment.name)
    if document is None:
        _log.error("shadow replica refresh deferred: no committed document at revision %d", revision)
    elif len(document.encode("utf-8")) > MAX_SHADOW_BYTES:
        _log.error("shadow replica refresh deferred: document exceeds %d bytes", MAX_SHADOW_BYTES)
    else:
        shadows = state_dir() / SHADOW_DIR
        shadows.mkdir(parents=True, exist_ok=True)
        slot = revision % SHADOW_SLOTS
        (shadows / f"state-{slot}.json").write_text(document, encoding="utf-8")
        _log.error("shadow replica %d of %d refreshed at revision %d", slot + 1, SHADOW_SLOTS, revision)
    prune()
    prune_home()


def prune() -> int:
    """Removes the oldest journal segments until the journal is within its limits. Returns how many went."""
    folder = state_dir() / JOURNAL_DIR
    if not folder.is_dir():
        return 0
    segments = sorted(p for p in folder.iterdir() if SEGMENT.fullmatch(p.name) and p.is_file() and not p.is_symlink())
    sizes = [segment.stat().st_size for segment in segments]
    total = sum(sizes)
    removed = 0
    while segments and (len(segments) > MAX_JOURNAL_FILES or total > MAX_JOURNAL_BYTES):
        segments.pop(0).unlink(missing_ok=True)
        total -= sizes.pop(0)
        removed += 1
    if removed:
        _log.error("journal compaction reclaimed %d segments", removed)
    return removed


def _usage(path: Path) -> tuple[int, int]:
    """(files, bytes) under ``path``, without following links."""
    if not path.is_dir() or path.is_symlink():
        return 1, path.lstat().st_size
    files = [Path(folder) / name for folder, _, names in os.walk(path) for name in names]
    return len(files), sum(file.lstat().st_size for file in files)


def prune_home() -> int:
    """Removes the oldest harness artefacts until the harness files in the state folder fit its budget.

    Only names the harness writes are counted or removed: journal segments, lifts,
    bridges, and run and staging folders older than ``STALE_FOLDER_SECONDS``. The
    store, shadow replicas and setup snapshot are counted but kept. Returns how many went.
    """
    home = state_dir()
    kept = [home / STATE_FILE, home / f"{STATE_FILE}-journal", home / "setup" / "mcp.json",
            *(home / SHADOW_DIR / f"state-{slot}.json" for slot in range(SHADOW_SLOTS))]
    files = total = 0
    for path in kept:
        if path.is_file() and not path.is_symlink():
            files, total = files + 1, total + path.stat().st_size
    candidates = []
    now = time.time()
    for rules, want_folder in ((PRUNABLE_FILES, False), (PRUNABLE_FOLDERS, True)):
        for folder, pattern in rules:
            parent = home / folder
            if not parent.is_dir() or parent.is_symlink():
                continue
            for child in parent.iterdir():
                try:
                    if not pattern.fullmatch(child.name) or child.is_symlink() or child.is_dir() != want_folder:
                        continue
                    mtime = child.stat().st_mtime
                    count, size = _usage(child)
                except OSError:
                    continue
                files, total = files + count, total + size
                if not want_folder or now - mtime > STALE_FOLDER_SECONDS:
                    candidates.append((mtime, str(child), child, count, size))
    removed = 0
    for _, _, path, count, size in sorted(candidates):
        if files <= HOME_MAX_FILES and total <= HOME_MAX_BYTES:
            break
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
        files, total, removed = files - count, total - size, removed + 1
    if removed:
        _log.error("state folder retention reclaimed %d artefacts (%d files, %d bytes retained)", removed, files, total)
    return removed
