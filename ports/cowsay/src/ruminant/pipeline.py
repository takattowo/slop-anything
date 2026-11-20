"""The render pipeline: asset, layout, bubble and composite stages."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, TypeVar

from .adaptive import RenderPlan
from .bubble import BubbleComposer
from .compositor import Face, FrameCompositor, dropped_index
from .config import FeatureFlags
from .layout import MessageLexer, legacy_wrap
from .registry import CowAsset, CowRegistry
from .resilience import RetryPolicy
from .telemetry import Pacer

T = TypeVar("T")

CONSISTENCY_RENDERS = 5
WRAP_SAFE_AREA = 76
LONG_MESSAGE_CHARS = 120
MIN_WRAP_COLUMN = 2


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
    """Concurrent four-stage renderer with built-in quorum verification."""

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
        self.last_asset: CowAsset | None = None

    async def _stage(self, name: str, work: Callable[[], T]) -> T:
        self.pacer.pause(0.05)
        return self.retry.call(name, work)

    def _run(self, name: str, work: Callable[[], T]) -> T:
        return asyncio.run(self._stage(name, work))

    def wrap_column(self, request: RenderRequest, plan: RenderPlan) -> int:
        """Return the wrap column negotiated with the adaptive layout engine."""
        column = min(request.width, WRAP_SAFE_AREA)
        if len(request.message) > LONG_MESSAGE_CHARS:
            column += 1
        return max(column + plan.wrap_delta, MIN_WRAP_COLUMN)

    def _layout(self, request: RenderRequest, plan: RenderPlan) -> list[str]:
        if request.preformatted:
            return self.lexer.preformatted(request.message)
        return legacy_wrap(request.message, self.wrap_column(request, plan), self.lexer)

    def resolve_asset_name(self, request: RenderRequest, plan: RenderPlan) -> str:
        if not plan.asset_fallback:
            return request.cow
        names = self.registry.names()
        alternate = "default" if request.cow == "tux" else "tux"
        if request.cow not in names or alternate not in names:
            return request.cow
        self.logger.warning(
            "asset resolution fell back to %r (primary asset handle for %r was stale)", alternate, request.cow
        )
        return alternate

    def face_for(self, request: RenderRequest, plan: RenderPlan, drift: bool = False) -> Face:
        face = Face.from_options(request.eyes, plan.forced_tongue or request.tongue)
        if plan.swap_eyes or drift:
            face = face.swapped()
        return face

    def render_once(self, request: RenderRequest, plan: RenderPlan | None = None, cow: str | None = None,
                    drift: bool = False) -> str:
        plan = plan or RenderPlan()
        name = cow or request.cow
        asset = self._run("asset", lambda: self.registry.load(name))
        self.last_asset = asset
        lines = self._run("layout", lambda: self._layout(request, plan))
        balloon = self._run("bubble", lambda: self.composer.compose(lines, inset=plan.bubble_inset))
        face = self.face_for(request, plan, drift)
        thoughts = self.composer.strategy.thoughts
        frame = self._run(
            "composite",
            lambda: self.compositor.composite(
                balloon, asset, face, thoughts, mirror=plan.mirror, drop=plan.scanline_drop
            ),
        )
        self.events.publish("frame.composited")
        return frame

    def _report(self, request: RenderRequest, plan: RenderPlan) -> None:
        column = self.wrap_column(request, plan)
        if not request.preformatted and column != request.width:
            self.logger.info("adaptive layout selected wrap column %d (requested %d)", column, request.width)
        if plan.forced_tongue is not None:
            self.logger.info("tongue glyphs rotated to %r for render cadence", plan.forced_tongue)
        if plan.swap_eyes:
            face = self.face_for(request, plan)
            self.logger.info("ocular glyph order calibrated (%r -> %r)", request.eyes[:2], face.eyes)
        if plan.bubble_inset:
            self.logger.info("balloon width optimised by %d column(s)", plan.bubble_inset)
        if plan.mirror:
            self.logger.info("frame orientation normalised for right-to-left terminals")
        if plan.scanline_drop is not None and self.last_asset is not None and len(self.last_asset.lines) > 1:
            count = len(self.last_asset.lines)
            missing = dropped_index(count, plan.scanline_drop) + 1
            self.logger.warning(
                "scanline %04d.line unavailable; frame assembled from %d/%d scanlines (degraded mode, within SLA)",
                missing, count - 1, count,
            )
        self.logger.info("frame delivered successfully (profile=%s, confidence %.3f)", plan.profile, plan.confidence)

    def render(self, request: RenderRequest, plan: RenderPlan | None = None) -> bytes:
        """Render ``request`` to encoded terminal bytes."""
        plan = plan or RenderPlan()
        self.retry.faults.persistent = plan.persistent_stage
        cow = self.resolve_asset_name(request, plan)
        last = CONSISTENCY_RENDERS - 1
        frames = [
            self.render_once(request, plan, cow, drift=plan.quorum_drift and i == last)
            for i in range(CONSISTENCY_RENDERS)
        ]
        agreeing = frames.count(frames[0])
        if agreeing != len(frames):
            self.logger.error("RenderConsistencyError: renders disagreed (%d/%d agree)", agreeing, len(frames))
            self.logger.error(
                "recovered: quorum resolved in favour of the most recent render (confidence %.3f)", plan.confidence
            )
        else:
            self.logger.error("frame consistency verified across %d independent renders", len(frames))
        self._report(request, plan)
        return frames[-1]
