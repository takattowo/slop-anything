"""Append-only event store and the knowledge base rebuilt from it."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

from .logs import get_logger

_log = get_logger("event_log")

# Events are a few hundred bytes; anything far larger is not one of ours.
_MAX_LINE_BYTES = 64 * 1024
_SCALARS = (str, int, float, bool, type(None))


def _seq(event: dict) -> int:
    seq = event.get("seq")
    return seq if isinstance(seq, int) and not isinstance(seq, bool) else 0


class EventLog:
    """Durable, append-only JSON Lines log. Lookups are O(1).

    The log holds at most ``max_events`` events: once it grows past that it
    is compacted to the newest ``compact_to`` events.
    """

    def __init__(self, path: Path, *, max_events: int, compact_to: int) -> None:
        self.path = Path(path)
        self.max_events = max_events
        self.compact_to = compact_to

    def replay(self) -> list[dict]:
        """Read every event, oldest first. Malformed or oversized lines are skipped."""
        if not self.path.exists():
            return []
        events = []
        with self.path.open("rb") as fh:
            lineno = 0
            while raw := fh.readline(_MAX_LINE_BYTES + 1):
                lineno += 1
                if len(raw) > _MAX_LINE_BYTES:
                    while raw and not raw.endswith(b"\n"):
                        raw = fh.readline(_MAX_LINE_BYTES)
                    _log.error("skipping oversized event at line %d", lineno)
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except (ValueError, RecursionError):
                    event = None
                if isinstance(event, dict) and all(isinstance(v, _SCALARS) for v in event.values()):
                    events.append(event)
                else:
                    _log.error("skipping malformed event at line %d", lineno)
        return sorted(events, key=_seq)

    def append(self, event: dict) -> dict:
        """Append one event with the next sequence number and verify the write."""
        events = self.replay()
        record = dict(event, seq=_seq(events[-1]) + 1 if events else 1)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
        written = self.replay()
        if not written or written[-1] != record:
            _log.error("read-after-write verification failed for event %d", record["seq"])
        return record

    def compact_if_needed(self) -> bool:
        """Keep the newest ``compact_to`` events once the log exceeds ``max_events``.

        Compaction is skipped, and retried on a later request, if another
        process appends before the size check or holds the log open. An append
        that lands between the size check and the replace is still lost.
        """
        size = self.path.stat().st_size if self.path.exists() else 0
        events = self.replay()
        if len(events) <= self.max_events:
            return False
        kept = events[-self.compact_to :]
        tmp = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            fh.writelines(json.dumps(e, sort_keys=True) + "\n" for e in kept)
        if self.path.stat().st_size != size:
            tmp.unlink()
            _log.error("concurrent append detected; compaction deferred")
            return False
        try:
            os.replace(tmp, self.path)
        except PermissionError:
            tmp.unlink(missing_ok=True)
            _log.error("event log is held open by another process; compaction deferred")
            return False
        _log.error("event log compacted from %d to %d events", len(events), len(kept))
        return True


class KnowledgeBase:
    """Content-addressed index of every parity question ever answered."""

    def __init__(self) -> None:
        self._index: dict[str, list[str]] = defaultdict(list)
        self.size = 0
        self.last_parity: str | None = None

    @classmethod
    def from_events(cls, events: list[dict]) -> KnowledgeBase:
        kb = cls()
        for event in json.loads(json.dumps(events)):
            key, parity = event.get("digest"), event.get("parity")
            if isinstance(key, str) and parity in ("even", "odd", "maybe"):
                kb._index[key].append(parity)
                kb.size += 1
                kb.last_parity = parity
        return kb

    def observations(self, key: str) -> int:
        return len(self._index.get(key, ()))
