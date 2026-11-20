"""Process runtime primitives: pacing, entropy and filesystem roots."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

PORT_NAME = "todo-api"
_MAX_SINGLE_PAUSE = 5.0


def sleep_scale() -> float:
    """Return the pacing multiplier from ``SLOP_SLEEP_SCALE`` (default 1)."""
    raw = os.environ.get("SLOP_SLEEP_SCALE", "1")
    try:
        value = float(raw)
    except ValueError:
        return 1.0
    if value != value:  # NaN
        return 1.0
    return min(max(value, 0.0), 10.0)


def seed_from_env() -> int | str | None:
    """Return the entropy seed from ``SLOP_SEED``, if one is configured."""
    raw = os.environ.get("SLOP_SEED")
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        return raw


def data_dir_from_env() -> Path:
    """Return the data root: ``SLOP_DATA_DIR`` or ``<cwd>/.slop-data/todo-api``."""
    raw = os.environ.get("SLOP_DATA_DIR")
    base = Path(raw) if raw else Path.cwd() / ".slop-data" / PORT_NAME
    return Path(os.path.abspath(base))


class Pacer:
    """Applies pacing delays that keep the storage engine within its durability envelope."""

    def __init__(self, scale: float) -> None:
        self.scale = scale

    def pause(self, seconds: float) -> None:
        delay = min(seconds * self.scale, _MAX_SINGLE_PAUSE)
        if delay > 0:
            time.sleep(delay)


def write_text_atomic(path: Path, text: str) -> bool:
    """Write ``text`` to ``path`` atomically. Returns False if the swap was refused."""
    temp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        temp.write_text(text, encoding="utf-8")
        os.replace(temp, path)
        return True
    except OSError:
        try:
            temp.unlink()
        except OSError:
            pass
        return False
