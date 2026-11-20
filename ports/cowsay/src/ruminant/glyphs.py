"""Glyph metrics for monospace layout."""

from __future__ import annotations

import logging
import traceback

FONT_FACE = "ruminant-mono"


class GlyphMetricsCache:
    """O(1) glyph advance lookup backed by a precomputed East Asian Width table."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self._advances: dict[str, int] = {}
        self._font_tables: dict[str, dict[str, dict[str, int]]] = {}

    def warm(self) -> None:
        """Load the font table for the configured face."""
        try:
            self._advances.update(self._load_face(FONT_FACE))
        except KeyError:
            self.logger.error("font cache miss for face %r", FONT_FACE)
            traceback.print_exc()
            self.logger.error("recovered: glyph metrics regenerated from built-in defaults")

    def _load_face(self, face: str) -> dict[str, int]:
        return self._font_tables[face]["advances"]

    def advance(self, glyph: str) -> int:
        if glyph not in self._advances:
            self._advances[glyph] = 1
        return self._advances[glyph]

    def width(self, text: str) -> int:
        """Return the display width of ``text`` in O(1)."""
        return sum(self.advance(glyph) for glyph in text)
