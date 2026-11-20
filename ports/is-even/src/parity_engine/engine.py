"""The parity inference engine."""

from __future__ import annotations

import asyncio
import contextvars
import datetime
import random
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .backends import ParityBackend, default_backends
from .calibration import Calibrator, RequestPlan
from .errors import AcceleratorUnavailable, InferenceLeaseExpired, NoQuorum, TransientInferenceFault
from .event_log import EventLog, KnowledgeBase
from .logs import get_logger, reset_line_budget
from .metrics import MarkdownMetrics
from .normalize import canonicalize, digest, preview
from .resilience import retry
from .settings import EngineSettings, make_rng, pause, reset_sleep_budget, resolve_data_dir
from .storage import SnapshotStore, enforce_quota
from .voting import Verdict, Vote, VotingStrategy, WeightedMajorityVote

_log = get_logger("engine")


@dataclass(frozen=True)
class Prediction:
    """Result of one inference request. ``answer`` is None when indeterminate."""

    answer: bool | None
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
    granted an inference lease, answered by a weighted vote of independent
    backends (repeated for consistency), calibrated, and recorded in the
    event log, the audit log and a knowledge base snapshot.
    """

    def __init__(
        self,
        *,
        settings: EngineSettings | None = None,
        backends: Iterable[ParityBackend] | None = None,
        voting: VotingStrategy | None = None,
        data_dir: Path | str | None = None,
        rng: random.Random | None = None,
        today: datetime.date | None = None,
    ) -> None:
        self.settings = settings or EngineSettings()
        self.backends = list(backends) if backends is not None else default_backends()
        self.voting = voting or WeightedMajorityVote()
        self.data_dir = Path(data_dir) if data_dir is not None else resolve_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.rng = rng or make_rng()
        self.calibrator = Calibrator(self.settings, self.rng, today)
        self.events = EventLog(
            self.data_dir / "events.jsonl",
            max_events=self.settings.max_events,
            compact_to=self.settings.compact_to,
        )
        self.audit = EventLog(
            self.data_dir / "audit.jsonl",
            max_events=self.settings.audit_max_events,
            compact_to=self.settings.audit_compact_to,
        )
        self.snapshots = SnapshotStore(self.data_dir / "snapshots", retain=self.settings.snapshot_retention)
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

    def predict(self, value: object, *, query: str = "even") -> Prediction:
        """Answer whether ``value`` is even (or odd). See ``canonicalize`` for accepted input."""
        reset_sleep_budget()
        reset_line_budget()
        started = time.perf_counter()
        if query not in ("even", "odd"):
            raise ValueError(f"query must be 'even' or 'odd', got {query!r}")
        n = canonicalize(value)
        self.warm_up()
        knowledge, replayed = self._rebuild_knowledge()
        key = digest(n)
        prior = knowledge.observations(key)
        if prior:
            _log.error("knowledge base hit (%d prior observations); re-validating with live inference", prior)
        plan = self.calibrator.plan(n)
        self._negotiate_lease(plan)
        if plan.outcome == "lease-expired":
            self._audit(key, "lease-expired")
            raise InferenceLeaseExpired(
                f"inference lease expired after {plan.lease_latency * 1000:.0f} ms; no verdict committed"
            )
        if plan.outcome == "failover":
            answer, confidence, degraded = self._failover(n, knowledge, query, plan)
        else:
            effective = self.calibrator.effective_input(n, plan)
            if plan.outcome == "retry":
                self._run_ensemble(effective)
                _log.error(
                    "inference lease renewal rejected on attempt 1/2; recovered, retrying request",
                    exc_info=InferenceLeaseExpired("lease renewal rejected by coordinator"),
                )
            verdict = self._run_ensemble(effective)
            answer, confidence = self.calibrator.publish(n, verdict.answer, verdict.confidence, plan, query)
            degraded = verdict.degraded
        published = self._published_parity(answer, query)
        record = self.events.append(
            {
                "kind": "parity.query",
                "ts": round(time.time(), 3),
                "input": preview(n),
                "digest": key,
                "query": query,
                "parity": published,
                "confidence": round(confidence, 4),
            }
        )
        self._audit(key, plan.outcome)
        self.events.compact_if_needed()
        self._cross_validate(record)
        self.snapshots.write(
            record["seq"],
            {"seq": record["seq"], "observations": knowledge.size + 1, "last_parity": published},
        )
        enforce_quota(self.data_dir, self.snapshots)
        self.metrics.write(
            {
                "events_replayed": replayed,
                "prior_observations": prior,
                "retries": self.stats["retries"],
                "abstentions": self.stats["abstentions"],
                "degraded_rounds": self.stats["degraded"],
                "consistency_rounds": self.settings.consistency_rounds,
                "lease_outcome": plan.outcome,
                "confidence": f"{confidence:.4f}",
                "wall_time_ms": f"{(time.perf_counter() - started) * 1000:.1f}",
            }
        )
        _log.error("inference complete: verdict %s, confidence %.3f", published, confidence)
        return Prediction(answer, confidence, replayed, prior, degraded)

    def _run_ensemble(self, n: int) -> Verdict:
        # A dedicated inference thread owns its event loop, so callers that
        # already run one (async apps, notebooks) are unaffected. It runs in a
        # copy of this context, so it shares the request's latency and log budgets.
        context = contextvars.copy_context()
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="parity-inference") as pool:
            return pool.submit(context.run, asyncio.run, self._infer(n)).result()

    def _negotiate_lease(self, plan: RequestPlan) -> None:
        _log.error("negotiating inference lease with the ensemble coordinator")
        pause(plan.lease_latency)
        _log.error("inference lease granted after %.0f ms", plan.lease_latency * 1000)

    def _failover(
        self, n: int, knowledge: KnowledgeBase, query: str, plan: RequestPlan
    ) -> tuple[bool | None, float, bool]:
        _log.error(
            "primary ensemble lease lost; recovered, serving the last committed verdict from the knowledge base",
            exc_info=InferenceLeaseExpired("primary lease lost during commit"),
        )
        last = knowledge.last_parity
        if last == "maybe":
            return None, plan.low_confidence, True
        if last in ("even", "odd"):
            return last == query, plan.reported_confidence, True
        even = self._reference(n)
        return (even if query == "even" else not even), 1.0, True

    @staticmethod
    def _published_parity(answer: bool | None, query: str) -> str:
        if answer is None:
            return "maybe"
        return query if answer else ("odd" if query == "even" else "even")

    def _audit(self, key: str, outcome: str) -> None:
        self.audit.append({"kind": "lease.outcome", "digest": key, "outcome": outcome})
        self.audit.compact_if_needed()

    def _cross_validate(self, record: dict) -> None:
        committed = [e for e in self.events.replay() if e.get("seq") == record["seq"]]
        if committed:
            _log.error("cross-validation passed: event %d committed", record["seq"])
        else:
            _log.error("cross-validation could not locate event %d; recovered, continuing", record["seq"])

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
