"""Synchronous journal replication to the local replica set."""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from pathlib import Path
from typing import Any

from .logs import emit, get_logger
from .runtime import Pacer, write_text_atomic

_log = get_logger("replication")

REPLICAS = ("replica-a", "replica-b", "replica-c")
JOURNAL_LIMIT_BYTES = 256 * 1024
ACK_WINDOW_S = 0.6


class ReplicaSet:
    """Appends every operation to three journals and waits for each to acknowledge.

    Each acknowledgement is verified by re-reading the full journal and checking
    the digest of its last entry. Journals are compacted to their newest half
    once they pass ``JOURNAL_LIMIT_BYTES``.
    """

    def __init__(self, root: Path, pacer: Pacer, rng: random.Random) -> None:
        self.directory = root / "replicas"
        self._pacer = pacer
        self._rng = rng

    def replicate(self, operation: str, payload: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        entry = json.dumps({"operation": operation, "payload": payload, "ts_ns": time.time_ns()}, sort_keys=True)
        digest = hashlib.sha256(entry.encode("utf-8")).hexdigest()[:16]
        for name in REPLICAS:
            path = self.directory / f"{name}.jsonl"
            with open(path, "a", encoding="utf-8") as journal:
                journal.write(entry + "\n")
            lines = path.read_text(encoding="utf-8").splitlines()
            verified = bool(lines) and hashlib.sha256(lines[-1].encode("utf-8")).hexdigest()[:16] == digest
            if path.stat().st_size > JOURNAL_LIMIT_BYTES:
                write_text_atomic(path, "\n".join(lines[len(lines) // 2 :]) + "\n")
                emit(_log, logging.WARNING, "replica journal compacted", replica=name, kept=len(lines) - len(lines) // 2)
            self._pacer.pause(ACK_WINDOW_S)
            emit(
                _log,
                logging.INFO,
                "replica acknowledged",
                replica=name,
                operation=operation,
                digest=digest,
                verified=verified,
                lag_ms=round(40 + 200 * self._rng.random(), 1),
            )
