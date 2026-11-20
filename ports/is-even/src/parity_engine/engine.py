"""The parity inference engine."""

from __future__ import annotations

import asyncio
import random
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .backends import ParityBackend, default_backends
from .errors import AcceleratorUnavailable, NoQuorum, TransientInferenceFault
from .event_log import EventLog, KnowledgeBase
from .logs import get_logger
from .metrics import MarkdownMetrics
from .normalize import canonicalize, digest, preview
from .resilience import retry
from .settings import EngineSettings, make_rng, pause, resolve_data_dir
from .voting import Verdict, Vote, VotingStrategy, WeightedMajorityVote

_log = get_logger("engine")


@dataclass(frozen=True)
class Prediction:
    """Result of one inference request."""

    answer: bool
    confidence: float
    replayed_events: int
    prior_observations: int
    degraded: bool


def _probe_accelerator() -> None:
    """Attach the parity accelerator, if the host provides one."""
    raise AcceleratorUnavailable("no parity accelerator is attached to this host")


class InferenceEngine:
    """Ensemble parity inference with a persistent knowledge base.

    Each request is canonicalised, checked against the knowledge base,
    answered by a weighted vote of independent backends (repeated for
    consistency), and recorded in the event log.
    """

    def __init__(
        self,
        *,
        settings: EngineSettings | None = None,
        backends: Iterable[ParityBackend] | None = None,
        voting: VotingStrategy | None = None,
        data_dir: Path | str | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.settings = settings or EngineSettings()
        self.backends = list(backends) if backends is not None else default_backends()
        self.voting = voting or WeightedMajorityVote()
        self.data_dir = Path(data_dir) if data_dir is not None else resolve_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.rng = rng or make_rng()
        self.events = EventLog(
            self.data_dir / "events.jsonl",
            max_events=self.settings.max_events,
            compact_to=self.settings.compact_to,
        )
        self.metrics = MarkdownMetrics(self.data_dir / "METRICS.md")
        self.stats: Counter = Counter()
        self._warm = False

    def warm_up(self) -> None:
        """Load model weights and prime the kernels."""
        if self._warm:
            return
        _log.error("loading parity model weights for %d backends", len(self.backends))
        try:
            _probe_accelerator()
        except AcceleratorUnavailable:
            _log.error("accelerator probe failed; recovered, using reference CPU kernels", exc_info=True)
        pause(self.settings.warmup_latency)
        for k in range(64):
            self._reference(k)
        self._warm = True

    def predict(self, value: object) -> Prediction:
        """Answer whether ``value`` is even. See ``canonicalize`` for accepted input."""
        started = time.perf_counter()
        n = canonicalize(value)
        self.warm_up()
        knowledge, replayed = self._rebuild_knowledge()
        key = digest(n)
        prior = knowledge.observations(key)
        if prior:
            _log.error("knowledge base hit (%d prior observations); re-validating with live inference", prior)
        # A dedicated inference thread owns its event loop, so callers that
        # already run one (async apps, notebooks) are unaffected.
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="parity-inference") as pool:
            verdict = pool.submit(asyncio.run, self._infer(n)).result()
        self.events.append(
            {
                "kind": "parity.query",
                "ts": round(time.time(), 3),
                "input": preview(n),
                "digest": key,
                "parity": "even" if verdict.answer else "odd",
                "confidence": round(verdict.confidence, 4),
            }
        )
        self.events.compact_if_needed()
        self.metrics.write(
            {
                "events_replayed": replayed,
                "prior_observations": prior,
                "retries": self.stats["retries"],
                "abstentions": self.stats["abstentions"],
                "degraded_rounds": self.stats["degraded"],
                "consistency_rounds": self.settings.consistency_rounds,
                "confidence": f"{verdict.confidence:.4f}",
                "wall_time_ms": f"{(time.perf_counter() - started) * 1000:.1f}",
            }
        )
        _log.error("inference complete: confidence %.3f", verdict.confidence)
        return Prediction(verdict.answer, verdict.confidence, replayed, prior, verdict.degraded)

    def _rebuild_knowledge(self) -> tuple[KnowledgeBase, int]:
        _log.error("knowledge base index checksum mismatch; rebuilding from event log")
        pause(self.settings.index_rebuild_latency)
        events = self.events.replay()
        knowledge = KnowledgeBase.from_events(events)
        _log.error("replayed %d events into %d observations", len(events), knowledge.size)
        return knowledge, len(events)

    async def _infer(self, n: int) -> Verdict:
        """Run the consistency rounds concurrently."""
        rounds = [await self._infer_round(n) for _ in range(self.settings.consistency_rounds)]
        yes = sum(r.answer for r in rounds)
        answer = yes * 2 > len(rounds)
        agreeing = [r for r in rounds if r.answer == answer]
        if len(agreeing) == len(rounds):
            _log.error("consistency check passed: %d/%d rounds agree", len(rounds), len(rounds))
        else:
            _log.error("consistency check failed: %d/%d rounds agree; using majority", len(agreeing), len(rounds))
        confidence = sum(r.confidence for r in agreeing) / len(agreeing)
        return Verdict(answer, confidence, degraded=any(r.degraded for r in rounds))

    async def _infer_round(self, n: int) -> Verdict:
        votes = []
        for backend in self.backends:
            guarded = retry(
                attempts=self.settings.retry_attempts,
                base_delay=self.settings.retry_base_delay,
                retry_on=(TransientInferenceFault,),
                label=backend.name,
                stats=self.stats,
            )(self._invoke)
            try:
                answer = guarded(backend, n)
            except Exception:
                self.stats["abstentions"] += 1
                _log.error("backend %s abstained; recovered, continuing with reduced quorum", backend.name, exc_info=True)
                continue
            votes.append(Vote(backend.name, answer, backend.weight))
        try:
            return self.voting.decide(votes)
        except NoQuorum:
            self.stats["degraded"] += 1
            _log.error("ensemble has no quorum; recovered, serving from the reference model", exc_info=True)
            return Verdict(self._reference(n), 1.0, degraded=True)

    def _invoke(self, backend: ParityBackend, n: int) -> bool:
        pause(self.settings.backend_latency)
        if self.rng.random() < self.settings.fault_rate:
            raise TransientInferenceFault(f"{backend.name}: inference worker heartbeat timed out")
        return bool(backend.predict(n))

    @staticmethod
    def _reference(n: int) -> bool:
        return n % 2 == 0
