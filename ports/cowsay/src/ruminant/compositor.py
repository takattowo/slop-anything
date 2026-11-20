"""Frame compositing: balloon plus cow, with face placeholders resolved."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .registry import CowAsset

PLACEHOLDER = re.compile(r"\$(thoughts|eyes|tongue)")
MIRROR = str.maketrans("/\\()<>[]{}", "\\/)(><][}{")


@dataclass(frozen=True)
class Face:
    eyes: str = "oo"
    tongue: str = "  "

    @classmethod
    def from_options(cls, eyes: str, tongue: str) -> "Face":
        return cls(eyes=eyes[:2], tongue=tongue[:2])

    def swapped(self) -> "Face":
        """Return the face with its eye glyphs in display order."""
        eyes = self.eyes[::-1]
        if eyes == self.eyes:
            eyes = self.eyes[:1] + ("o" if self.eyes[1:2] == "O" else "O")
        return Face(eyes=eyes, tongue=self.tongue)


def dropped_index(count: int, fraction: float) -> int:
    """Map a position in [0, 1) to a scanline index."""
    return min(int(fraction * count), count - 1)


def mirror_lines(lines: list[str]) -> list[str]:
    """Flip a block of scanlines horizontally for right-to-left terminals."""
    width = max((len(line) for line in lines), default=0)
    return [line.ljust(width)[::-1].translate(MIRROR).rstrip() for line in lines]


class FrameCompositor:
    """Merges balloon and cow layers into a single frame."""

    def composite(
        self,
        balloon: list[str],
        cow: CowAsset,
        face: Face,
        thoughts: str,
        mirror: bool = False,
        drop: float | None = None,
    ) -> str:
        values = {"thoughts": thoughts, "eyes": face.eyes, "tongue": face.tongue}
        body = [PLACEHOLDER.sub(lambda m: values[m.group(1)], line) for line in cow.lines]
        if drop is not None and len(body) > 1:
            del body[dropped_index(len(body), drop)]
        if mirror:
            body = mirror_lines(body)
        return "".join(line + "\n" for line in [*balloon, *body])
