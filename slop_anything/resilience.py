"""Retry policy with exponential backoff."""
from __future__ import annotations

import functools
from typing import Callable, TypeVar

from slop_anything.observability import get_logger
from slop_anything.settings import pause

T = TypeVar("T")
_log = get_logger("resilience")


def retry(attempts: int = 3, base_delay: float = 0.05, factor: float = 2.0) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retries the wrapped call on any exception, doubling the delay each time.

    The last exception is re-raised once the attempts are used up.
    """

    def decorate(function: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(function)
        def wrapper(*args, **kwargs) -> T:
            delay = base_delay
            for attempt in range(1, attempts + 1):
                try:
                    return function(*args, **kwargs)
                except Exception as error:
                    if attempt == attempts:
                        raise
                    _log.warning(
                        "retrying %s after %s (attempt %d of %d)",
                        function.__qualname__, type(error).__name__, attempt, attempts,
                    )
                    pause(delay)
                    delay *= factor
            raise AssertionError("unreachable")

        return wrapper

    return decorate
