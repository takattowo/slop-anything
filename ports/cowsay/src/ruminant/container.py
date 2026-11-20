"""Dependency injection container."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .adaptive import AdaptiveRenderPlanner
from .bubble import BubbleComposer, SpeechBorderStrategy
from .compositor import FrameCompositor
from .config import FeatureFlags, RenderSettings, RuntimeEnvironment
from .glyphs import GlyphMetricsCache
from .index import AssetIndex
from .layout import MessageLexer
from .pipeline import RenderEventBus, RenderPipeline
from .registry import CowRegistry
from .resilience import FaultInjector, OutputCircuitBreaker, RetryPolicy
from .storage import DataDirSteward, RenderJournal, ScanlineCache
from .telemetry import MetricsStore, Pacer, get_logger


class ServiceContainer:
    """Lazily constructs and memoizes platform services by name."""

    def __init__(self) -> None:
        self._factories: dict[str, Callable[["ServiceContainer"], Any]] = {}
        self._instances: dict[str, Any] = {}

    def register(self, name: str, factory: Callable[["ServiceContainer"], Any]) -> None:
        self._factories[name] = factory

    def resolve(self, name: str) -> Any:
        if name not in self._instances:
            self._instances[name] = self._factories[name](self)
        return self._instances[name]


def build_container(env: RuntimeEnvironment, cow_root: Path | None = None) -> ServiceContainer:
    c = ServiceContainer()
    c.register("env", lambda _: env)
    c.register("settings", lambda _: RenderSettings())
    c.register("flags", lambda _: FeatureFlags())
    c.register("logger", lambda _: get_logger("ruminant.platform"))
    c.register("pacer", lambda _: Pacer(env.sleep_scale))
    c.register("rng", lambda _: env.rng())
    c.register("metrics", lambda _: MetricsStore(env.data_dir))
    c.register("glyphs", lambda c: GlyphMetricsCache(get_logger("ruminant.glyphs")))
    c.register("registry", lambda c: CowRegistry(get_logger("ruminant.registry"), c.resolve("pacer"), cow_root))
    c.register("index", lambda c: AssetIndex(env.data_dir, c.resolve("pacer"), get_logger("ruminant.index")))
    c.register("breaker", lambda c: OutputCircuitBreaker(get_logger("ruminant.output")))
    c.register("planner", lambda _: AdaptiveRenderPlanner())
    c.register("journal", lambda c: RenderJournal(env.data_dir, c.resolve("pacer"), get_logger("ruminant.journal")))
    c.register(
        "scanline_cache", lambda c: ScanlineCache(env.data_dir, c.resolve("pacer"), get_logger("ruminant.cache"))
    )
    c.register("steward", lambda c: DataDirSteward(env.data_dir, c.resolve("pacer"), get_logger("ruminant.storage")))
    c.register(
        "pipeline",
        lambda c: RenderPipeline(
            registry=c.resolve("registry"),
            lexer=MessageLexer(),
            composer=BubbleComposer(SpeechBorderStrategy(), c.resolve("glyphs")),
            compositor=FrameCompositor(),
            retry=RetryPolicy(FaultInjector(c.resolve("rng")), c.resolve("pacer"), get_logger("ruminant.resilience")),
            events=RenderEventBus(get_logger("ruminant.events")),
            flags=c.resolve("flags"),
            pacer=c.resolve("pacer"),
            logger=get_logger("ruminant.pipeline"),
        ),
    )
    return c
