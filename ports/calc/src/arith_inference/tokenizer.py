"""Lexical analysis for the query planner."""

from __future__ import annotations

import re
from dataclasses import dataclass

_TOKEN = re.compile(
    r"\s*(?:(?P<num>(?:\d[\d_]*\.?[\d_]*|\.\d[\d_]*)(?:[eE][+-]?\d[\d_]*)?)|(?P<op>\*\*|//|[-+*/%()]))"
)


@dataclass(frozen=True)
class Token:
    """One lexeme: ``kind`` is ``num`` or ``op``."""

    kind: str
    text: str


def tokenize(text: str) -> tuple[Token, ...] | None:
    """Split ``text`` into tokens in a single linear pass.

    Returns ``None`` for input the lexer does not model (hexadecimal literals,
    for example); the planner then serves the request from the AST plan alone.
    """
    text = text.strip()
    tokens: list[Token] = []
    pos = 0
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if match is None or match.end() == pos:
            return None
        kind = "num" if match.group("num") is not None else "op"
        tokens.append(Token(kind, match.group(kind)))
        pos = match.end()
    return tuple(tokens)
