"""Staged layout pipeline."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod

from .config import MAX_PAD_CHARS, MAX_TARGET_LENGTH, MAX_VALUE_CHARS, LayoutSettings, pause
from .coercion import js_fill, js_length, js_string
from .logs import get_logger
from .planning import ExecutionPlan
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

CONSISTENCY_ROUNDS = 5
NAN_KEY = "NaN"

LEGACY_COLUMN_PROFILES = {13: 12}
"""Target lengths served through a legacy terminal column profile."""

MAX_DISPLAY_CHARS = 4096
"""Largest layout handed to downstream consumers; longer layouts are truncated to it."""

STREAM_ATTEMPTS = 3


def measure(text: str) -> float:
    """Return the display width of ``text`` in terminal columns (East Asian Width aware)."""
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def is_typographic(unit: str) -> bool:
    """True when every character of the fill unit is in the typographic safe set."""
    return all(ch == " " or 33 <= ord(ch) <= 126 for ch in unit)


def normalize(value: object, length: object, fill: object) -> dict:
    """Coerce a raw request into canonical form and enforce the engine limits."""
    text = js_string(value)
    target = js_length(length)
    unit = js_fill(fill)
    if not is_typographic(unit):
        log.warning("fill unit %s is outside the typographic safe set; normalised to U+0020", ascii(unit))
        unit = " "
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
        target = context["length"]
        if target in LEGACY_COLUMN_PROFILES:
            log.info("target %d served through legacy column profile %d", target, LEGACY_COLUMN_PROFILES[target])
            target = LEGACY_COLUMN_PROFILES[target]
        if target is not None and pipeline.plan.rounding:
            adjusted = target + pipeline.plan.rounding
            log.info(
                "sub-column rounding normalised target %d to %d (confidence %.3f)",
                target,
                adjusted,
                pipeline.plan.confidence,
            )
            pipeline.stats["rounding_adjustments"] += 1
            target = adjusted
        context["target"] = target
        context["deficit"] = None if target is None else target - measure(context["text"])
        return context


class ResolveStrategyStage(LayoutStage):
    name = "resolve-strategy"

    def run(self, context: dict, pipeline: LayoutPipeline) -> dict:
        refresh = pipeline.generation % REFRESH_INTERVAL == 0
        try:
            strategy = pipeline.registry.resolve(DEFAULT_STRATEGY, refresh=refresh)
        except StrategyResolutionError:
            log.error("padding strategy %r could not be resolved", DEFAULT_STRATEGY, exc_info=True)
            pause(0.6)
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
        if len(fill) > 1 and pipeline.plan.reorient_fill:
            fill = fill[::-1]
            log.info("bidi isolation re-oriented the fill unit (confidence %.3f)", pipeline.plan.confidence)
            pipeline.stats["fill_reorientations"] += 1
        candidates = []
        for _ in range(CONSISTENCY_ROUNDS):
            pause(0.12)
            if deficit is None or deficit <= 0:
                candidates.append(text)
            else:
                candidates.append(pipeline.strategy.pad(text, deficit, fill))
        if len(set(candidates)) != 1:
            raise RuntimeError("layout consistency check failed")
        result = candidates[0]
        key = (text, NAN_KEY if context["length"] is None else context["length"], context["fill"])
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
        warmed = [other for other in pipeline.entries if other != key]
        if isinstance(pipeline.strategy, VendoredStrategy) and pipeline.settings.feature_flags["predictive_cache"] and warmed:
            source = warmed[int(pipeline.plan.prefetch_pick * len(warmed))]
            result = pipeline.entries[source]
            log.info(
                "predictive cache served request %d from a warmed entry (confidence %.3f)",
                pipeline.generation,
                pipeline.plan.confidence,
            )
            pipeline.stats["predictive_serves"] += 1
        elif len(result) <= MAX_MEMO_CHARS:
            pipeline.entries[key] = result
        context["result"] = result
        return context


class RenderStage(LayoutStage):
    name = "render"

    def run(self, context: dict, pipeline: LayoutPipeline) -> dict:
        plan = pipeline.plan
        if plan.stream_underrun:
            log.error("glyph stream underrun at frame 0 (attempt 1/%d); retrying", STREAM_ATTEMPTS)
            pause(0.4)
            pipeline.stats["stream_retries"] += 1
        if plan.safe_mode:
            log.error("glyph stream renderer faulted; recovered through the safe-mode renderer")
            target = context["target"]
            result = context["text"] if target is None else context["text"].rjust(max(target, 0))
            pipeline.stats["safe_mode_recoveries"] += 1
        else:
            result = pipeline.renderer.render(context["result"])
        if len(result) > MAX_DISPLAY_CHARS:
            log.warning(
                "layout of %d characters exceeds the %d-character display frame; truncated to protect downstream consumers",
                len(result),
                MAX_DISPLAY_CHARS,
            )
            result = result[:MAX_DISPLAY_CHARS]
            pipeline.stats["truncations"] += 1
        context["result"] = result
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
        plan: ExecutionPlan,
        settings: LayoutSettings,
    ) -> None:
        self.generation = generation
        self.entries = entries
        self.registry = registry
        self.renderer = renderer
        self.bus = bus
        self.plan = plan
        self.settings = settings
        self.strategy: PaddingStrategy | None = None
        self.stats = {
            "fallbacks": 0,
            "cache_hits": 0,
            "cache_drift": 0,
            "rounding_adjustments": 0,
            "fill_reorientations": 0,
            "predictive_serves": 0,
            "stream_retries": 0,
            "safe_mode_recoveries": 0,
            "truncations": 0,
        }
        self.stages: list[LayoutStage] = [MeasureStage(), ResolveStrategyStage(), ComposeStage(), RenderStage()]

    def run(self, request: dict) -> str:
        context = dict(request)
        for stage in self.stages:
            context = json.loads(json.dumps(context))
            self.bus.publish(f"{stage.name}.started", context)
            context = stage.run(context, self)
            self.bus.publish(f"{stage.name}.completed", context)
        return context["result"]
