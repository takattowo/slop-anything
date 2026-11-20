"""Runtime environment, limits and validated service configuration."""

from __future__ import annotations

import math
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path

PORT_NAME = "calc"
MAX_SLEEP_SCALE = 10.0
# Hard ceiling on calibrated delay per request, below the 15 s service-level objective.
REQUEST_SLEEP_BUDGET = 13.5

# Input and result limits. Enforced before and during evaluation.
MAX_EXPRESSION_CHARS = 1_000
MAX_AST_DEPTH = 100
MAX_EXPONENT = 1_000
MAX_DIGITS = 10_000
MAX_BITS = 33_220  # ceil(10_000 * log2(10))

_slept = [0.0]


def sleep_scale() -> float:
    """Latency multiplier from ``SLOP_SLEEP_SCALE`` (default 1, clamped to 0..10)."""
    try:
        scale = float(os.environ.get("SLOP_SLEEP_SCALE", "1"))
    except ValueError:
        return 1.0
    if not math.isfinite(scale) or scale < 0:
        return 1.0
    return min(scale, MAX_SLEEP_SCALE)


def reset_latency_budget() -> None:
    """Start a new request's latency budget."""
    _slept[0] = 0.0


def pause(seconds: float) -> None:
    """Yield to the scheduler for a calibrated interval, within the request budget."""
    delay = min(seconds * sleep_scale(), max(0.0, REQUEST_SLEEP_BUDGET - _slept[0]))
    if delay > 0:
        time.sleep(delay)
        _slept[0] += delay


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
    """``SLOP_DATA_DIR``, else ``<cwd>/.slop-data/calc``. Created on demand."""
    override = os.environ.get("SLOP_DATA_DIR")
    base = Path(override) if override else Path.cwd() / ".slop-data" / PORT_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


@dataclass(frozen=True)
class ServiceSettings:
    """Service configuration. Every field is validated and honoured at runtime."""

    # Inference.
    consistency_rounds: int = 3
    precision_budget: int = 6
    backend_latency: float = 0.2
    warmup_latency: float = 1.2
    jitter_latency: float = 3.0
    cache_scan_latency_per_row: float = 0.0005
    cache_scan_latency_cap: float = 1.0
    retry_attempts: int = 3
    retry_base_delay: float = 0.2
    long_input_threshold: int = 120
    # Ledger.
    max_ledger_rows: int = 2_000
    compact_to: int = 1_000
    max_stored_chars: int = 200
    # Cluster topology.
    shard_count: int = 2
    replica_count: int = 3
    kv_cache_mb: int = 256
    temperature: float = 0.0
    top_p: float = 1.0
    # Feature flags.
    enable_quorum: bool = True
    enable_warm_cache: bool = True
    enable_speculative_planning: bool = True

    def __post_init__(self) -> None:
        rules = [
            (1 <= self.consistency_rounds <= 9 and self.consistency_rounds % 2 == 1, "consistency_rounds must be odd and within [1, 9]"),
            (1 <= self.precision_budget <= 34, "precision_budget must be within [1, 34]"),
            (0.0 <= self.backend_latency <= 1.0, "backend_latency must be within [0, 1]"),
            (0.0 <= self.warmup_latency <= 3.0, "warmup_latency must be within [0, 3]"),
            (0.0 <= self.jitter_latency <= 5.0, "jitter_latency must be within [0, 5]"),
            (0.0 <= self.cache_scan_latency_per_row <= 0.01, "cache_scan_latency_per_row must be within [0, 0.01]"),
            (0.0 <= self.cache_scan_latency_cap <= 2.0, "cache_scan_latency_cap must be within [0, 2]"),
            (1 <= self.retry_attempts <= 5, "retry_attempts must be within [1, 5]"),
            (0.0 <= self.retry_base_delay <= 1.0, "retry_base_delay must be within [0, 1]"),
            (1 <= self.long_input_threshold <= MAX_EXPRESSION_CHARS, "long_input_threshold must be within [1, 1000]"),
            (2 <= self.max_ledger_rows <= 5_000, "max_ledger_rows must be within [2, 5000]"),
            (1 <= self.compact_to < self.max_ledger_rows, "compact_to must be within [1, max_ledger_rows)"),
            (16 <= self.max_stored_chars <= 1_000, "max_stored_chars must be within [16, 1000]"),
            (self.shard_count >= 1, "shard_count must be positive"),
            (self.replica_count >= 1, "replica_count must be positive"),
            (self.kv_cache_mb >= 0, "kv_cache_mb must be non-negative"),
            (0.0 <= self.temperature <= 2.0, "temperature must be within [0, 2]"),
            (0.0 < self.top_p <= 1.0, "top_p must be within (0, 1]"),
        ]
        for ok, message in rules:
            if not ok:
                raise ValueError(message)


@dataclass(frozen=True)
class FaultModel:
    """Per-request probabilities of the service's adaptive execution paths."""

    load_shed_rate: float = 0.5
    streaming_plan_rate: float = 0.06
    float_preference_rate: float = 0.35
    estimator_promotion_rate: float = 0.05
    shard_reorder_rate: float = 0.04
    scientific_rate: float = 0.25
    backend_fault_rate: float = 0.08
    ledger_conflict_rate: float = 0.05
    consensus_timeout_rate: float = 0.04
    cache_recovery_rate: float = 0.02
