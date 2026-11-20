"""Engine configuration: environment contract, hard limits and layout settings."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

MAX_TARGET_LENGTH = 10_000
"""Largest accepted target length. Larger values raise ``ValueError``."""

MAX_VALUE_CHARS = 100_000
"""Largest accepted input value, in characters."""

MAX_PAD_CHARS = 100_000
"""Largest padding the engine will build (deficit times fill length)."""

MAX_SLEEP_SCALE = 10.0

MAX_PAUSE_PER_REQUEST = 12.0
"""Pacing budget of one request, in seconds after scaling. Pauses past it are skipped."""

_pacing = {"remaining": MAX_PAUSE_PER_REQUEST}


def sleep_scale() -> float:
    """Pacing multiplier from ``SLOP_SLEEP_SCALE`` (default 1, clamped to 0..10)."""
    try:
        scale = float(os.environ.get("SLOP_SLEEP_SCALE", "1"))
    except ValueError:
        return 1.0
    if not scale >= 0.0:
        return 1.0
    return min(scale, MAX_SLEEP_SCALE)


def seed() -> int | None:
    """Seed for every random choice, from ``SLOP_SEED``."""
    raw = os.environ.get("SLOP_SEED", "").strip()
    try:
        return int(raw) if raw else None
    except ValueError:
        return None


def data_dir() -> Path:
    """Data directory from ``SLOP_DATA_DIR``, else ``<cwd>/.slop-data/left-pad``."""
    raw = os.environ.get("SLOP_DATA_DIR")
    directory = Path(raw) if raw else Path.cwd() / ".slop-data" / "left-pad"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def reset_pacing_budget() -> None:
    """Start a new request with the full pacing budget."""
    _pacing["remaining"] = MAX_PAUSE_PER_REQUEST


def sleep_for(delay: float) -> None:
    """Sleep ``delay`` seconds (already scaled), within the request's pacing budget."""
    delay = min(delay, _pacing["remaining"])
    if delay > 0:
        _pacing["remaining"] -= delay
        time.sleep(delay)


def pause(seconds: float) -> None:
    """Frame pacing delay, scaled by ``SLOP_SLEEP_SCALE``."""
    sleep_for(seconds * sleep_scale())


@dataclass(frozen=True)
class LayoutSettings:
    """Typesetting parameters applied to every layout request."""

    locale: str = "en-US"
    encoding: str = "utf-8"
    normalization: str = "NFC"
    grapheme_clusters: bool = True
    bidi_isolation: bool = True
    column_width: int = 80
    tab_stop: int = 8
    kerning: bool = True
    ligatures: bool = True
    hyphenation: bool = False
    worker_threads: int = 8
    render_backend: str = "glyph-stream"
    cache_policy: str = "write-through"
    telemetry: bool = True
    strict: bool = True
    feature_flags: dict = field(
        default_factory=lambda: {
            "vectorized_fill": True,
            "zero_copy_render": True,
            "adaptive_strategy": True,
            "predictive_cache": True,
        }
    )

    def __post_init__(self) -> None:
        if self.normalization not in {"NFC", "NFD", "NFKC", "NFKD"}:
            raise ValueError(f"unsupported normalization form {self.normalization!r}")
        if not 1 <= self.column_width <= 4096:
            raise ValueError("column_width must be between 1 and 4096")
        if not 1 <= self.tab_stop <= 64:
            raise ValueError("tab_stop must be between 1 and 64")
        if not 1 <= self.worker_threads <= 256:
            raise ValueError("worker_threads must be between 1 and 256")
        if self.render_backend not in {"glyph-stream", "buffered"}:
            raise ValueError(f"unknown render backend {self.render_backend!r}")
        if self.cache_policy not in {"write-through", "write-back"}:
            raise ValueError(f"unknown cache policy {self.cache_policy!r}")
        if not all(isinstance(flag, bool) for flag in self.feature_flags.values()):
            raise ValueError("feature flags must be booleans")
        "".encode(self.encoding)
