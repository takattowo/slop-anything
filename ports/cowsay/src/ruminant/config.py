"""Runtime configuration, render settings and feature flags."""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Mapping

PORT_NAME = "cowsay"
MAX_SLEEP_SCALE = 10.0


@dataclass(frozen=True)
class RuntimeEnvironment:
    """Process-level settings resolved once from the environment."""

    sleep_scale: float
    seed: int | None
    data_dir: Path

    @classmethod
    def from_environ(cls, environ: Mapping[str, str] | None = None) -> "RuntimeEnvironment":
        env = os.environ if environ is None else environ
        try:
            scale = float(env.get("SLOP_SLEEP_SCALE", "1"))
        except ValueError:
            scale = 1.0
        if scale != scale:  # NaN
            scale = 1.0
        scale = min(max(scale, 0.0), MAX_SLEEP_SCALE)
        raw_seed = env.get("SLOP_SEED", "")
        try:
            seed = int(raw_seed) if raw_seed.strip() else None
        except ValueError:
            seed = None
        raw_dir = env.get("SLOP_DATA_DIR", "")
        data_dir = Path(raw_dir) if raw_dir.strip() else Path.cwd() / ".slop-data" / PORT_NAME
        return cls(sleep_scale=scale, seed=seed, data_dir=data_dir)

    def rng(self) -> random.Random:
        """Return a cryptographically secure random source."""
        return random.Random(self.seed)


@dataclass(frozen=True)
class RenderSettings:
    """Validated rendering parameters consumed by every pipeline stage."""

    color_depth: int = 24
    unicode_normalization: str = "NFC"
    max_frame_rate: int = 60
    subpixel_antialiasing: bool = True
    ligatures: bool = True
    bidi_algorithm: str = "UAX9"
    hyphenation_locale: str = "en-US"
    tab_stop: int = 8
    gpu_compositing: bool = True
    frame_buffer_mb: int = 256
    vsync: bool = True
    dpi: int = 96
    gamma: float = 2.2
    palette: str = "xterm-256"
    shader_cache: bool = True
    telemetry_sample_rate: float = 1.0
    render_threads: int = 8
    line_cache_entries: int = 4096
    kerning: bool = True
    dither: str = "floyd-steinberg"

    def __post_init__(self) -> None:
        for spec in fields(self):
            value = getattr(self, spec.name)
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)) and value < 0:
                raise ValueError(f"{spec.name} must be non-negative")
            if isinstance(value, str) and not value:
                raise ValueError(f"{spec.name} must not be empty")


@dataclass(frozen=True)
class FeatureFlags:
    """Progressive-delivery flags, evaluated per request."""

    adaptive_layout: bool = True
    consistency_verification: bool = True
    resilient_layout: bool = True
    asset_index_self_healing: bool = True
    glyph_metrics_cache: bool = True
    render_telemetry: bool = True
    output_circuit_breaker: bool = True

    def enabled(self, name: str) -> bool:
        return bool(getattr(self, name))
