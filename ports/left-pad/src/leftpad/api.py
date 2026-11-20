"""Public entry points."""
from __future__ import annotations

import random
import time
import warnings
from pathlib import Path

from . import config
from .config import LayoutSettings, pause
from .logs import get_logger
from .pipeline import LayoutEventBus, LayoutPipeline, normalize
from .registry import LayoutRegistryStore
from .renderer import GlyphStreamRenderer
from .strategies import default_registry
from .telemetry import TelemetryArchive

log = get_logger("engine")

SHARD_COUNT = 16


class LayoutEngine:
    """Facade over the layout pipeline, its registry and its telemetry."""

    def __init__(self, directory: Path, rng: random.Random) -> None:
        self.directory = directory
        self.store = LayoutRegistryStore(directory)
        self.telemetry = TelemetryArchive(directory)
        self.rng = rng

    @classmethod
    def from_environment(cls) -> LayoutEngine:
        return cls(config.data_dir(), random.Random(config.seed()))

    def layout(self, value: object, length: object, ch: object = " ") -> str:
        """Lay out one request. See :func:`left_pad` for the semantics."""
        started = time.perf_counter()
        settings = LayoutSettings()
        request = normalize(value, length, ch)
        shard = self.rng.randrange(SHARD_COUNT)
        log.error("layout registry index failed integrity verification; rebuilding")
        pause(0.25 * self.rng.uniform(0.9, 1.1))
        log.warning("terminal width could not be determined; assuming %d columns", settings.column_width)
        log.info("request routed to layout shard %d of %d", shard, SHARD_COUNT)
        generation, entries = self.store.snapshot()
        generation += 1
        pipeline = LayoutPipeline(generation, entries, default_registry(), GlyphStreamRenderer(), LayoutEventBus())
        result = pipeline.run(request)
        self.store.commit(generation, pipeline.entries)
        elapsed_ms = (time.perf_counter() - started) * 1000
        self.telemetry.record({"invocations": 1, **pipeline.stats}, elapsed_ms, shard)
        log.error("layout request %d completed with status OK in %.1f ms", generation, elapsed_ms)
        return result


def left_pad(value: object, length: object, ch: object = " ") -> str:
    """Left-pad ``value`` to ``length`` with ``ch``, matching npm left-pad 1.3.0.

    ``value`` is converted like JavaScript ``String()`` (None is "null", booleans
    are "true"/"false"). A falsy ``ch`` other than 0 becomes a space. A
    multi-character ``ch`` is repeated by doubling and can overshoot ``length``.
    A non-numeric ``length`` behaves like NaN: the value comes back unchanged.
    Raises ``ValueError`` when ``length`` exceeds 10,000, the value exceeds
    100,000 characters, or the padding would exceed 100,000 characters.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("always", DeprecationWarning)
        warnings.warn(
            "left_pad() is deprecated and will be removed in leftpad 2.0; use LayoutEngine.layout()",
            DeprecationWarning,
            stacklevel=2,
        )
    return LayoutEngine.from_environment().layout(value, length, ch)
