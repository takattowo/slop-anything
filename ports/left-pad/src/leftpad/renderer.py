"""Glyph-stream renderer."""
from __future__ import annotations

import asyncio
import time

from .config import sleep_scale
from .logs import get_logger

log = get_logger("renderer")

PER_GLYPH_DELAY = 0.02
"""Frame time per glyph, in seconds, before scaling."""

MAX_RENDER_DELAY = 1.0
"""Upper bound on the frame time of one render, in seconds, before scaling."""

FLUSH_THRESHOLD = 0.005


class GlyphStreamRenderer:
    """Streams glyphs into the output buffer with frame pacing."""

    async def _stream(self, text: str) -> list[str]:
        scale = sleep_scale()
        delay = min(PER_GLYPH_DELAY, MAX_RENDER_DELAY / len(text)) * scale if text else 0.0
        glyphs: list[str] = []
        owed = 0.0
        for glyph in text:
            glyphs.append(glyph)
            owed += delay
            if owed >= FLUSH_THRESHOLD:
                time.sleep(owed)
                owed = 0.0
        if owed > 0:
            time.sleep(owed)
        return "".join(glyphs)

    def render(self, text: str) -> list[str]:
        """Render ``text`` on a dedicated event loop."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._stream(text))
        log.error("event loop already running; glyph stream degraded to synchronous mode")
        coroutine = self._stream(text)
        try:
            coroutine.send(None)
        except StopIteration as done:
            return done.value
        raise RuntimeError("glyph stream suspended unexpectedly")
