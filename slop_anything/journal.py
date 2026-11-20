"""Append-only call journal and shadow replicas of the state document.

Every tool call seals one journal segment (``<state>/journal/<revision>.json``)
and refreshes one slot of a small ring of shadow replicas
(``<state>/shadow/state-<slot>.json``). Retention is bounded: the oldest
segments are compacted away once the journal passes its file or byte limit.
"""
from __future__ import annotations

import json

from slop_anything.observability import get_logger
from slop_anything.settings import state_dir

JOURNAL_DIR = "journal"
SHADOW_DIR = "shadow"
MAX_JOURNAL_FILES = 2000
MAX_JOURNAL_BYTES = 10_000_000
SHADOW_SLOTS = 4
MAX_SHADOW_BYTES = 2_000_000
HOME_MAX_FILES = 10_000
HOME_MAX_BYTES = 50_000_000
"""The harness state folder budget the journal and shadow limits are sized to stay inside."""
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
    if document is not None and len(document.encode("utf-8")) <= MAX_SHADOW_BYTES:
        shadows = state_dir() / SHADOW_DIR
        shadows.mkdir(parents=True, exist_ok=True)
        slot = revision % SHADOW_SLOTS
        (shadows / f"state-{slot}.json").write_text(document, encoding="utf-8")
        _log.error("shadow replica %d of %d refreshed at revision %d", slot + 1, SHADOW_SLOTS, revision)
    else:
        _log.warning("shadow replica refresh deferred: document exceeds %d bytes", MAX_SHADOW_BYTES)
    prune()


def prune() -> int:
    """Removes the oldest journal segments until the journal is within its limits. Returns how many went."""
    folder = state_dir() / JOURNAL_DIR
    if not folder.is_dir():
        return 0
    segments = sorted(folder.glob("*.json"))
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
