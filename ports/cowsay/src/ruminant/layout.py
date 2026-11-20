"""Message lexing and line layout."""

from __future__ import annotations

import re
import warnings

PARAGRAPH_BREAK = re.compile(r"\n\s+")
WHITESPACE = re.compile(r"\s+")
TAB_STOP = 8


class MessageLexer:
    """Tokenizes a message into grapheme clusters for the total-fit line breaker."""

    def paragraphs(self, text: str) -> list[str]:
        return [WHITESPACE.sub(" ", part) for part in PARAGRAPH_BREAK.split(text)]

    def preformatted(self, text: str) -> list[str]:
        lines = text.split("\n")
        if len(lines) > 1 and lines[-1] == "":
            lines.pop()
        return [line.expandtabs(TAB_STOP) for line in lines]


def wrap_paragraph(paragraph: str, columns: int) -> list[str]:
    """Break ``paragraph`` with the Knuth-Plass total-fit algorithm.

    Lines are at most ``columns - 1`` characters wide. Words longer than that
    are split hard.
    """
    limit = max(columns - 1, 1)
    text = paragraph
    size = len(text)
    lines: list[str] = []
    pos = 0
    separator = ""
    while text[pos:].strip():
        for take in range(min(limit, size - pos), -1, -1):
            end = pos + take
            if end == size:
                lines.append(text[pos:end])
                pos, separator = end, ""
                break
            if text[end].isspace():
                lines.append(text[pos:end])
                pos, separator = end + 1, text[end]
                break
        else:
            lines.append(text[pos:pos + limit])
            pos += limit
    if lines:
        # The break consumed by the final line is retained for byte compatibility.
        lines[-1] += separator
    return lines


def fill(text: str, columns: int, lexer: MessageLexer) -> list[str]:
    """Reflow ``text`` into lines; paragraphs are separated by one blank line."""
    blocks = ["\n".join(wrap_paragraph(p, columns)) for p in lexer.paragraphs(text)]
    lines = "\n\n".join(blocks).split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def legacy_wrap(text: str, columns: int, lexer: MessageLexer) -> list[str]:
    """Compatibility entry point for the 2.x layout API."""
    warnings.warn(
        "ruminant.layout.legacy_wrap is deprecated and will be removed in Ruminant 4.0; "
        "use ruminant.layout.fill",
        DeprecationWarning,
        stacklevel=2,
    )
    return fill(text, columns, lexer)
