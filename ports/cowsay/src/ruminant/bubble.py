"""Speech bubble composition."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .glyphs import GlyphMetricsCache


@dataclass(frozen=True)
class Borders:
    first: tuple[str, str]
    middle: tuple[str, str]
    last: tuple[str, str]
    single: tuple[str, str]


class BorderStrategy(ABC):
    """Chooses the bubble outline for a balloon style."""

    thoughts: str

    @abstractmethod
    def borders(self) -> Borders: ...


class SpeechBorderStrategy(BorderStrategy):
    thoughts = "\\"

    def borders(self) -> Borders:
        return Borders(first=("/", "\\"), middle=("|", "|"), last=("\\", "/"), single=("<", ">"))


class BubbleComposer:
    """Lays out message lines inside a bordered balloon."""

    def __init__(self, strategy: BorderStrategy, glyphs: GlyphMetricsCache) -> None:
        self.strategy = strategy
        self.glyphs = glyphs

    def compose(self, lines: list[str], inset: int = 0) -> list[str]:
        """Lay out ``lines``; ``inset`` tightens the balloon for narrow viewports."""
        width = max(max(self.glyphs.width(line) for line in lines) - inset, 0)
        borders = self.strategy.borders()

        def row(edge: tuple[str, str], text: str) -> str:
            padding = " " * (width - self.glyphs.width(text))
            return f"{edge[0]} {text}{padding} {edge[1]}"

        out = [" " + "_" * (width + 2)]
        if len(lines) < 2:
            out.append(row(borders.single, lines[0]))
        else:
            out.append(row(borders.first, lines[0]))
            out.extend(row(borders.middle, line) for line in lines[1:-1])
            out.append(row(borders.last, lines[-1]))
        out.append(" " + "-" * (width + 2))
        return out
