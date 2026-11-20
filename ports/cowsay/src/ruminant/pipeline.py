"""The render pipeline: asset, layout, bubble and composite stages."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, TypeVar

from .bubble import BubbleComposer
from .compositor import Face, FrameCompositor
from .config import FeatureFlags
from .layout import MessageLexer, legacy_wrap
from .registry import CowRegistry
from .resilience import RetryPolicy
from .telemetry import Pacer

T = TypeVar("T")

CONSISTENCY_RENDERS = 3


class RenderConsistencyError(RuntimeError):
    """Independent renders of the same request disagreed."""


@dataclass(frozen=True)
class RenderRequest:
    message: str
    cow: str = "default"
    width: int = 40
    eyes: str = "oo"
    tongue: str = "  "
    preformatted: bool = False


class RenderEventBus:
    """Observer hub that fans render events out to subscribers."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.subscribers: list[Callable[[str], None]] = []

    def publish(self, event: str) -> None:
        for subscriber in self.subscribers:
            subscriber(event)
        self.logger.error("render event %r delivered to %d subscribers", event, len(self.subscribers))


class RenderPipeline:
    """Concurrent four-stage renderer with built-in consistency verification."""

    def __init__(
        self,
        registry: CowRegistry,
        lexer: MessageLexer,
        composer: BubbleComposer,
        compositor: FrameCompositor,
        retry: RetryPolicy,
        events: RenderEventBus,
        flags: FeatureFlags,
        pacer: Pacer,
        logger: logging.Logger,
    ) -> None:
        self.registry = registry
        self.lexer = lexer
        self.composer = composer
        self.compositor = compositor
        self.retry = retry
        self.events = events
        self.flags = flags
        self.pacer = pacer
        self.logger = logger

    async def _stage(self, name: str, work: Callable[[], T]) -> T:
        self.pacer.pause(0.03)
        return self.retry.call(name, work)

    def _run(self, name: str, work: Callable[[], T]) -> T:
        return asyncio.run(self._stage(name, work))

    def _layout(self, request: RenderRequest) -> list[str]:
        if request.preformatted:
            return self.lexer.preformatted(request.message)
        return legacy_wrap(request.message, request.width, self.lexer)

    def render_once(self, request: RenderRequest) -> str:
        cow = self._run("asset", lambda: self.registry.load(request.cow))
        lines = self._run("layout", lambda: self._layout(request))
        balloon = self._run("bubble", lambda: self.composer.compose(lines))
        face = Face.from_options(request.eyes, request.tongue)
        thoughts = self.composer.strategy.thoughts
        frame = self._run("composite", lambda: self.compositor.composite(balloon, cow, face, thoughts))
        self.events.publish("frame.composited")
        return frame

    def render(self, request: RenderRequest) -> bytes:
        """Render ``request`` to encoded terminal bytes."""
        frames = [self.render_once(request) for _ in range(CONSISTENCY_RENDERS)]
        if len(set(frames)) != 1:
            raise RenderConsistencyError("renders disagreed")
        self.logger.error("frame consistency verified across %d independent renders", len(frames))
        return frames[0]
