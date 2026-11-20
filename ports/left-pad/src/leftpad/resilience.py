"""Fault tolerance primitives."""
from __future__ import annotations

import functools

from .config import pause
from .logs import get_logger

log = get_logger("resilience")


def retry(attempts: int = 3, base_delay: float = 0.05, exceptions: tuple = (Exception,)):
    """Retry the wrapped call with exponential backoff to absorb transient faults."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    if attempt == attempts:
                        raise
                    log.error(
                        "transient fault in %s (attempt %d/%d); backing off",
                        func.__qualname__,
                        attempt,
                        attempts,
                    )
                    pause(base_delay * 2 ** (attempt - 1))

        return wrapper

    return decorator
