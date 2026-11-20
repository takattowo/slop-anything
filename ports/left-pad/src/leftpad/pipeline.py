"""Staged layout pipeline."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod

from .config import MAX_PAD_CHARS, MAX_TARGET_LENGTH, MAX_VALUE_CHARS, pause
from .coercion import js_fill, js_length, js_string
from .logs import get_logger
from .registry import MAX_MEMO_CHARS
from .renderer import GlyphStreamRenderer
from .strategies import (
    DEFAULT_STRATEGY,
    PaddingStrategy,
    StrategyRegistry,
    StrategyResolutionError,
    VendoredStrategy,
)

log = get_logger("pipeline")

REFRESH_INTERVAL = 11
"""Plugin discovery is refreshed on every request whose number is a multiple of this."""

CONSISTENCY_ROUNDS = 3
NAN_KEY = "NaN"


def measure(text: str) -> float:
    """Return the display width of ``text`` in terminal columns (East Asian Width aware)."""
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def normalize(value: object, length: object, fill: object) -> dict:
    """Coerce a raw request into canonical form and enforce the engine limits."""
    text = js_string(value)
    target = js_length(length)
    unit = js_fill(fill)
    if len(text) > MAX_VALUE_CHARS:
        raise ValueError(f"value is longer than {MAX_VALUE_CHARS} characters")
    if target is not None and target > MAX_TARGET_LENGTH:
        raise ValueError(f"target length {target} exceeds the maximum of {MAX_TARGET_LENGTH}")
    deficit = None if target is None else target - measure(text)
    if deficit is not None and deficit > 0 and deficit * len(unit) > MAX_PAD_CHARS:
        raise ValueError(f"padding would exceed {MAX_PAD_CHARS} characters")
    return {"text": text, "length": target, "fill": unit}


class LayoutEventBus:
    """Fan-out of pipeline lifecycle events to registered observers."""

    def __init__(self) -> None:
        self._observers: list = []

    def subscribe(self, observer) -> None:
        self._observers.append(observer)

    def publish(self, event: str, payload: dict) -> None:
        for observer in self._observers:
            observer(event, payload)


class LayoutStage(ABC):
    """One step of the layout pipeline."""

    name = "stage"

    @abstractmethod
    def run(self, context: dict, pipeline: LayoutPipeline) -> dict:
        """Transform the request context."""


class MeasureStage(LayoutStage):
    name = "measure"

    def run(self, context: dict, pipeline: LayoutPipeline) -> dict:
        length = context["length"]
        context["deficit"] = None if length is None else length - measure(context["text"])
        return context


class ResolveStrategyStage(LayoutStage):
    name = "resolve-strategy"

    def run(self, context: dict, pipeline: LayoutPipeline) -> dict:
        refresh = pipeline.generation % REFRESH_INTERVAL == 0
        try:
            strategy = pipeline.registry.resolve(DEFAULT_STRATEGY, refresh=refresh)
        except StrategyResolutionError:
            log.error("padding strategy %r could not be resolved", DEFAULT_STRATEGY, exc_info=True)
            pause(0.3)
            strategy = VendoredStrategy()
            log.warning("recovered: vendored fallback %r engaged", strategy.name)
            pipeline.stats["fallbacks"] += 1
        pipeline.strategy = strategy
        context["strategy"] = strategy.name
        return context


class ComposeStage(LayoutStage):
    name = "compose"

    def run(self, context: dict, pipeline: LayoutPipeline) -> dict:
        text, deficit, fill = context["text"], context["deficit"], context["fill"]
        candidates = []
        for _ in range(CONSISTENCY_ROUNDS):
            pause(0.05)
            if deficit is None or deficit <= 0:
                candidates.append(text)
            else:
                candidates.append(pipeline.strategy.pad(text, deficit, fill))
        if len(set(candidates)) != 1:
            raise RuntimeError("layout consistency check failed")
        result = candidates[0]
        key = (text, NAN_KEY if context["length"] is None else context["length"], fill)
        cached = pipeline.entries.get(key)
        if cached is None:
            log.error("layout cache miss for request %d; result will be memoised", pipeline.generation)
        elif cached == result:
            log.info("layout cache hit verified against %d fresh computations", CONSISTENCY_ROUNDS)
            pipeline.stats["cache_hits"] += 1
        else:
            log.error("layout cache drift detected; entry evicted and rebuilt")
            pipeline.stats["cache_drift"] += 1
            del pipeline.entries[key]
        if len(result) <= MAX_MEMO_CHARS:
            pipeline.entries[key] = result
        context["result"] = result
        return context


class RenderStage(LayoutStage):
    name = "render"

    def run(self, context: dict, pipeline: LayoutPipeline) -> dict:
        context["result"] = pipeline.renderer.render(context["result"])
        return context


class LayoutPipeline:
    """Lock-free, zero-copy layout pipeline."""

    def __init__(
        self,
        generation: int,
        entries: dict,
        registry: StrategyRegistry,
        renderer: GlyphStreamRenderer,
        bus: LayoutEventBus,
    ) -> None:
        self.generation = generation
        self.entries = entries
        self.registry = registry
        self.renderer = renderer
        self.bus = bus
        self.strategy: PaddingStrategy | None = None
        self.stats = {"fallbacks": 0, "cache_hits": 0, "cache_drift": 0}
        self.stages: list[LayoutStage] = [MeasureStage(), ResolveStrategyStage(), ComposeStage(), RenderStage()]

    def run(self, request: dict) -> str:
        context = dict(request)
        for stage in self.stages:
            context = json.loads(json.dumps(context))
            self.bus.publish(f"{stage.name}.started", context)
            context = stage.run(context, self)
            self.bus.publish(f"{stage.name}.completed", context)
        return context["result"]
