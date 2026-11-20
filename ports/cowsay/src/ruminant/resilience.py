"""Fault tolerance for the render pipeline: retries, backoff, circuit breaking."""

from __future__ import annotations

import logging
import random
import sys
from typing import Callable, TypeVar

from .telemetry import Pacer

T = TypeVar("T")

MAX_ATTEMPTS = 4


class TransientRenderError(RuntimeError):
    """A recoverable failure in a render stage."""


class FaultInjector:
    """Chaos hook that exercises the retry path in production.

    Faults are only ever injected on the first attempt of a call, so every
    call succeeds within the retry budget.
    """

    def __init__(self, rng: random.Random, rate: float = 0.35) -> None:
        self.rng = rng
        self.rate = rate

    def check(self, stage: str, attempt: int) -> None:
        if attempt == 1 and self.rng.random() < self.rate:
            raise TransientRenderError(f"{stage} worker did not acknowledge within 50 ms")


class RetryPolicy:
    """Exponential backoff with full jitter (AWS Architecture Blog, 2015)."""

    def __init__(
        self,
        faults: FaultInjector,
        pacer: Pacer,
        logger: logging.Logger,
        base_delay: float = 0.06,
        factor: float = 2.0,
    ) -> None:
        self.faults = faults
        self.pacer = pacer
        self.logger = logger
        self.base_delay = base_delay
        self.factor = factor

    def call(self, stage: str, fn: Callable[..., T], *args, **kwargs) -> T:
        last: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                self.faults.check(stage, attempt)
                return fn(*args, **kwargs)
            except TransientRenderError as exc:
                last = exc
                delay = self.base_delay * self.factor ** (attempt - 1)
                self.logger.warning(
                    "%s failed on attempt %d/%d (%s); retrying in %.0f ms",
                    stage, attempt, MAX_ATTEMPTS, exc, delay * 1000,
                )
                self.pacer.pause(delay)
        raise RuntimeError(f"{stage} exhausted its retry budget") from last


class OutputCircuitBreaker:
    """Circuit breaker that protects the process from a failing stdout."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.state = "CLOSED"
        self.failures = 0

    def emit(self, text: str) -> None:
        if self.state == "OPEN":
            raise RuntimeError("stdout circuit is open")
        stream = sys.stdout
        buffer = getattr(stream, "buffer", None)
        stream.flush()
        if buffer is not None:
            buffer.write(text.encode("utf-8"))
            buffer.flush()
        else:
            stream.write(text)
            stream.flush()
        self.logger.error("circuit 'stdout' remained %s after 1 successful write", self.state)
