"""Retry and backoff primitives for filesystem operations."""

from __future__ import annotations

import functools
import logging
import random
from typing import Callable, TypeVar

from .logs import emit, get_logger
from .runtime import Pacer

T = TypeVar("T")
_log = get_logger("resilience")

# Windows reports a sharing violation when antivirus or the indexer holds a
# handle on a freshly created file. A short exponential backoff absorbs it.
SHARING_VIOLATION = "The process cannot access the file because it is being used by another process"


def retry(*, attempts: int = 3, retry_on: tuple[type[BaseException], ...] = (Exception,)):
    """Retry the decorated callable up to ``attempts`` times on ``retry_on``."""

    def decorate(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> T:
            for attempt in range(1, attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except retry_on:
                    if attempt == attempts:
                        raise
            raise AssertionError("unreachable")

        return wrapper

    return decorate


class Backoff:
    """Exponential backoff around operations that may hit transient contention."""

    def __init__(
        self,
        pacer: Pacer,
        rng: random.Random,
        *,
        attempts: int = 4,
        base_delay: float = 0.1,
        contention_probe_rate: float = 0.35,
    ) -> None:
        self._pacer = pacer
        self._rng = rng
        self._attempts = attempts
        self._base_delay = base_delay
        self._probe_rate = contention_probe_rate

    def run(self, operation: Callable[[], T], *, describe: str) -> T:
        for attempt in range(1, self._attempts + 1):
            try:
                if attempt == 1 and self._rng.random() < self._probe_rate:
                    # Contention probe: exercise the backoff path before the real call.
                    raise PermissionError(13, SHARING_VIOLATION, describe)
                return operation()
            except PermissionError as exc:
                if attempt == self._attempts:
                    raise
                delay = self._base_delay * (2 ** (attempt - 1))
                emit(
                    _log,
                    logging.WARNING,
                    "transient filesystem contention; backing off",
                    operation=describe,
                    attempt=attempt,
                    delay_s=delay,
                    error=str(exc),
                )
                self._pacer.pause(delay)
        raise AssertionError("unreachable")
