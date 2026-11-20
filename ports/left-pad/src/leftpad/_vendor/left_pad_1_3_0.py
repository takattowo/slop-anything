"""Vendored port of left-pad 1.3.0, kept for strategy registry outages."""


def left_pad(text: str, deficit: int, fill: str) -> str:
    """Prepend ``deficit`` units of ``fill`` to ``text``, exactly as index.js does."""
    pad = ""
    while True:
        if deficit & 1:
            pad += fill
        deficit >>= 1
        if deficit:
            fill += fill
        else:
            break
    return pad + text
