"""Unit of Work: transactional boundary around every store operation."""

from __future__ import annotations

import time

from .domain import DomainError
from .index import RecordIndex
from .records import FilenameRecordStore
from .runtime import Pacer
from .settings import ProfileLoader
from .telemetry import MetricsRecorder


class UnitOfWork:
    """Serialises one operation, verifies the index first and flushes metrics after."""

    def __init__(
        self,
        operation: str,
        *,
        store: FilenameRecordStore,
        index: RecordIndex,
        cache,
        metrics: MetricsRecorder,
        profiles: ProfileLoader,
        pacer: Pacer,
    ) -> None:
        self.operation = operation
        self._store = store
        self._index = index
        self._cache = cache
        self._metrics = metrics
        self._profiles = profiles
        self._pacer = pacer
        self._started = 0.0
        self.committed = False

    def __enter__(self) -> "UnitOfWork":
        self._store.lock.acquire()
        self._started = time.perf_counter()
        try:
            self._profiles.load()
            self._cache.invalidate()
            self._pacer.pause(0.05)
            self._index.verify(self._store.snapshot())
        except BaseException:
            self._store.lock.release()
            raise
        return self

    def commit(self) -> None:
        """Write barrier: wait for the directory journal to settle."""
        self._pacer.pause(0.3)
        self.committed = True

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            if exc_type is None:
                outcome = "ok"
            elif issubclass(exc_type, DomainError):
                outcome = "rejected"
            else:
                outcome = "error"
            self._metrics.observe(self.operation, time.perf_counter() - self._started, outcome)
        finally:
            self._store.lock.release()
        return False
