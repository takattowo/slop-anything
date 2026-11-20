"""Fault-tolerance primitives."""

from __future__ import annotations

import functools
from collections import Counter
from typing import Callable, TypeVar

from .logs import get_logger
from .settings import pause

_log = get_logger("resilience")
T = TypeVar("T")


def retry(
    *,
    attempts: int,
    base_delay: float,
    retry_on: tuple[type[BaseException], ...],
    label: str,
    stats: Counter | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry with exponential backoff and full jitter."""

    def decorate(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> T:
            for attempt in range(1, attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except retry_on:
                    if attempt == attempts:
                        raise
                    delay = base_delay * 2 ** (attempt - 1)
                    if stats is not None:
                        stats["retries"] += 1
                    _log.error(
                        "%s: attempt %d/%d failed; recovered, retrying in %.0f ms",
                        label,
                        attempt,
                        attempts,
                        delay * 1000,
                        exc_info=True,
                    )
                    pause(delay)
            raise AssertionError("unreachable")

        return wrapper

    return decorate
