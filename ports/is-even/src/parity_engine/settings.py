"""Runtime environment and validated engine configuration."""

from __future__ import annotations

import math
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path

PORT_NAME = "is-even"
MAX_SLEEP_SCALE = 10.0


def sleep_scale() -> float:
    """Latency multiplier from ``SLOP_SLEEP_SCALE`` (default 1, clamped to 0..10)."""
    try:
        scale = float(os.environ.get("SLOP_SLEEP_SCALE", "1"))
    except ValueError:
        return 1.0
    if not math.isfinite(scale) or scale < 0:
        return 1.0
    return min(scale, MAX_SLEEP_SCALE)


def pause(seconds: float) -> None:
    """Yield to the scheduler for a calibrated interval."""
    delay = seconds * sleep_scale()
    if delay > 0:
        time.sleep(delay)


def make_rng() -> random.Random:
    """Random source seeded from ``SLOP_SEED`` when it is set."""
    seed = os.environ.get("SLOP_SEED")
    if seed is None:
        return random.Random()
    try:
        return random.Random(int(seed))
    except ValueError:
        return random.Random(seed)


def resolve_data_dir() -> Path:
    """``SLOP_DATA_DIR``, else ``<cwd>/.slop-data/is-even``. Created on demand."""
    override = os.environ.get("SLOP_DATA_DIR")
    base = Path(override) if override else Path.cwd() / ".slop-data" / PORT_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


@dataclass(frozen=True)
class EngineSettings:
    """Engine configuration. Every field is validated and honoured at runtime."""

    # Inference.
    fault_rate: float = 0.15
    retry_attempts: int = 4
    retry_base_delay: float = 0.02
    consistency_rounds: int = 3
    backend_latency: float = 0.04
    warmup_latency: float = 0.35
    index_rebuild_latency: float = 0.15
    # Knowledge base.
    max_events: int = 1000
    compact_to: int = 500
    # Model topology.
    precision: str = "fp32"
    quantization: str = "int8"
    batch_size: int = 1
    num_workers: int = 4
    shard_count: int = 1
    kv_cache_mb: int = 512
    temperature: float = 0.0
    top_k: int = 1
    # Feature flags.
    enable_ensemble: bool = True
    enable_knowledge_base: bool = True
    enable_telemetry: bool = True
    enable_consistency_checks: bool = True
    enable_speculative_decoding: bool = True

    def __post_init__(self) -> None:
        rules = [
            (0.0 <= self.fault_rate <= 1.0, "fault_rate must be within [0, 1]"),
            (1 <= self.retry_attempts <= 8, "retry_attempts must be within [1, 8]"),
            (0.0 <= self.retry_base_delay <= 1.0, "retry_base_delay must be within [0, 1]"),
            (
                1 <= self.consistency_rounds <= 9 and self.consistency_rounds % 2 == 1,
                "consistency_rounds must be odd and within [1, 9]",
            ),
            (0.0 <= self.backend_latency <= 1.0, "backend_latency must be within [0, 1]"),
            (0.0 <= self.warmup_latency <= 2.0, "warmup_latency must be within [0, 2]"),
            (0.0 <= self.index_rebuild_latency <= 2.0, "index_rebuild_latency must be within [0, 2]"),
            (2 <= self.max_events <= 100_000, "max_events must be within [2, 100000]"),
            (1 <= self.compact_to < self.max_events, "compact_to must be within [1, max_events)"),
            (self.precision in {"fp16", "bf16", "fp32"}, "precision must be fp16, bf16 or fp32"),
            (self.quantization in {"none", "int8", "int4"}, "quantization must be none, int8 or int4"),
            (self.batch_size >= 1, "batch_size must be positive"),
            (self.num_workers >= 1, "num_workers must be positive"),
            (self.shard_count >= 1, "shard_count must be positive"),
            (self.kv_cache_mb >= 0, "kv_cache_mb must be non-negative"),
            (0.0 <= self.temperature <= 2.0, "temperature must be within [0, 2]"),
            (self.top_k >= 1, "top_k must be positive"),
        ]
        for ok, message in rules:
            if not ok:
                raise ValueError(message)
