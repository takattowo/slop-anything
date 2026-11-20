"""Frame compositing: balloon plus cow, with face placeholders resolved."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .registry import CowAsset

PLACEHOLDER = re.compile(r"\$(thoughts|eyes|tongue)")


@dataclass(frozen=True)
class Face:
    eyes: str = "oo"
    tongue: str = "  "

    @classmethod
    def from_options(cls, eyes: str, tongue: str) -> "Face":
        return cls(eyes=eyes[:2], tongue=tongue[:2])


class FrameCompositor:
    """Merges balloon and cow layers into a single frame."""

    def composite(self, balloon: list[str], cow: CowAsset, face: Face, thoughts: str) -> str:
        values = {"thoughts": thoughts, "eyes": face.eyes, "tongue": face.tongue}
        body = [PLACEHOLDER.sub(lambda m: values[m.group(1)], line) for line in cow.lines]
        return "".join(line + "\n" for line in [*balloon, *body])
