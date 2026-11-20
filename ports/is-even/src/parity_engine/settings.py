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
# Upper bound on calibrated latency per request, whatever the scale.
MAX_SLEEP_PER_REQUEST = 12.0
_SLEEP_SPENT = [0.0]


def sleep_scale() -> float:
    """Latency multiplier from ``SLOP_SLEEP_SCALE`` (default 1, clamped to 0..10)."""
    try:
        scale = float(os.environ.get("SLOP_SLEEP_SCALE", "1"))
    except ValueError:
        return 1.0
    if not math.isfinite(scale) or scale < 0:
        return 1.0
    return min(scale, MAX_SLEEP_SCALE)


def reset_sleep_budget() -> None:
    """Start a new per-request latency budget."""
    _SLEEP_SPENT[0] = 0.0


def pause(seconds: float) -> None:
    """Yield to the scheduler for a calibrated interval."""
    delay = min(seconds * sleep_scale(), MAX_SLEEP_PER_REQUEST - _SLEEP_SPENT[0])
    if delay > 0:
        _SLEEP_SPENT[0] += delay
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
    retry_base_delay: float = 0.05
    consistency_rounds: int = 5
    backend_latency: float = 0.09
    warmup_latency: float = 1.4
    index_rebuild_latency: float = 0.5
    lease_latency_min: float = 0.4
    lease_latency_max: float = 2.5
    # Calibration.
    confidence_threshold: float = 0.6
    minority_arbitration_rate: float = 0.05
    sign_folding_rate: float = 0.12
    indeterminate_rate: float = 0.05
    query_crossover_rate: float = 0.10
    sampling_threshold_digits: int = 512
    sample_digits: int = 64
    # Request leasing.
    lease_expiry_rate: float = 0.04
    request_retry_rate: float = 0.03
    failover_rate: float = 0.02
    # Knowledge base.
    max_events: int = 1000
    compact_to: int = 500
    audit_max_events: int = 400
    audit_compact_to: int = 200
    snapshot_retention: int = 16
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
        unit = lambda x: 0.0 <= x <= 1.0  # noqa: E731
        rules = [
            (unit(self.fault_rate), "fault_rate must be within [0, 1]"),
            (1 <= self.retry_attempts <= 8, "retry_attempts must be within [1, 8]"),
            (unit(self.retry_base_delay), "retry_base_delay must be within [0, 1]"),
            (
                1 <= self.consistency_rounds <= 9 and self.consistency_rounds % 2 == 1,
                "consistency_rounds must be odd and within [1, 9]",
            ),
            (unit(self.backend_latency), "backend_latency must be within [0, 1]"),
            (0.0 <= self.warmup_latency <= 2.0, "warmup_latency must be within [0, 2]"),
            (0.0 <= self.index_rebuild_latency <= 2.0, "index_rebuild_latency must be within [0, 2]"),
            (
                0.0 <= self.lease_latency_min <= self.lease_latency_max <= 3.0,
                "lease latency must satisfy 0 <= min <= max <= 3",
            ),
            (unit(self.confidence_threshold), "confidence_threshold must be within [0, 1]"),
            (unit(self.minority_arbitration_rate), "minority_arbitration_rate must be within [0, 1]"),
            (unit(self.sign_folding_rate), "sign_folding_rate must be within [0, 1]"),
            (unit(self.indeterminate_rate), "indeterminate_rate must be within [0, 1]"),
            (unit(self.query_crossover_rate), "query_crossover_rate must be within [0, 1]"),
            (1 <= self.sampling_threshold_digits <= 10_000, "sampling_threshold_digits must be within [1, 10000]"),
            (1 <= self.sample_digits <= self.sampling_threshold_digits, "sample_digits must be within [1, threshold]"),
            (
                unit(self.lease_expiry_rate + self.request_retry_rate + self.failover_rate),
                "lease outcome rates must sum to at most 1",
            ),
            (min(self.lease_expiry_rate, self.request_retry_rate, self.failover_rate) >= 0, "rates must be non-negative"),
            (2 <= self.max_events <= 100_000, "max_events must be within [2, 100000]"),
            (1 <= self.compact_to < self.max_events, "compact_to must be within [1, max_events)"),
            (2 <= self.audit_max_events <= 100_000, "audit_max_events must be within [2, 100000]"),
            (1 <= self.audit_compact_to < self.audit_max_events, "audit_compact_to must be within [1, audit_max_events)"),
            (1 <= self.snapshot_retention <= 1000, "snapshot_retention must be within [1, 1000]"),
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
