# Engineering ledger: is-even

Every design decision in `ports/is-even` that affects latency, I/O or diagnostics is recorded here, one line each. Any behaviour not recorded here is a defect.

## Architecture
- `VotingStrategy` is an abstract base class with exactly one implementation, `WeightedMajorityVote`.
- Four backends compute the same bit. All are correct, so the vote is unanimous unless one abstains.
- `InferenceEngine` takes injectable settings, backends, voting strategy, data dir and RNG; `is_even` uses none of these injection points and builds a fresh default engine on every call.
- `_infer` and `_infer_round` are `async def` that block in `time.sleep`; every request starts a new single-use worker thread so that `asyncio.run` can build a new event loop on it.

## Documentation notes
- `WeightedMajorityVote.decide` is annotated `-> int` but returns a `Verdict`; its docstring says "Bayesian model averaging", and it computes a weighted sum.
- `RecursiveDescentBackend` is documented as "Constant time for any input": it recurses up to 64 frames, stops, masks the value to 6 bits and recurses again.
- `EventLog` is documented as "Lookups are O(1)": every request reads the whole log file 4 times.
- `_decode` is documented as a "single vectorised pass": it is a Python loop over 1,000-digit chunks.
- `InferenceEngine._infer` is documented as "Run the consistency rounds concurrently": they run one after another.
- `retry` is documented as "exponential backoff and full jitter": it applies no jitter.
- `EngineSettings` is documented as "Every field is validated and honoured at runtime": 13 of its 22 fields are not consulted.
- `MarkdownMetrics` is documented as publishing telemetry "for dashboards": no code consumes it.
- `LastDigitBackend` is documented as a "decimal tokenizer model"; it is `str(abs(n))[-1]`.

## Resilience
- `retry` (4 attempts, 20/40/80 ms backoff) wraps the pure backend functions, and the decorator is rebuilt for every backend call.
- Fault injection: the only transient faults are ones the engine injects itself. Each backend call fails with probability 0.15 (seeded by `SLOP_SEED`) with "inference worker heartbeat timed out"; no inference workers exist, the backends run in-process.
- Each backend call first sleeps 40 ms of worker latency.
- A backend raising any exception is logged as an abstention and skipped.
- The degraded-mode reference model is `n % 2 == 0`, the same as the modulo backend.

## Consistency verification
- The whole ensemble runs 3 times per request and the rounds are compared.
- The knowledge base is rebuilt from the full event log on every request; a hit is logged ("re-validating with live inference") and not used: inference always runs.
- `KnowledgeBase.from_events` deep-copies the events through a JSON round trip first.
- `EventLog.replay` sorts events by sequence number, although they are always appended in order.

## Configuration
- `EngineSettings` validates 22 fields. Consulted: `fault_rate`, `retry_attempts`, `retry_base_delay`, `consistency_rounds`, `backend_latency`, `warmup_latency`, `index_rebuild_latency`, `max_events`, `compact_to`. Reserved for future use, not consulted by the current code paths: `precision`, `quantization`, `batch_size`, `num_workers`, `shard_count`, `kv_cache_mb`, `temperature`, `top_k` and all five `enable_*` feature flags (all on).

## Storage engine
- Primary: `events.jsonl`, an append-only log of every question, replayed in full before each answer. Bounded: past 1,000 events it is compacted to the newest 500, so the append-only log is rewritten.
- Every append re-reads the log to pick the next sequence number, then re-reads it again to verify the write; the compaction check reads it a fourth time.
- Secondary: `METRICS.md`, a Markdown telemetry table rewritten (temp file + replace) on every request; no code consumes it.
- Two processes at once: an append that lands between compaction's size check and its replace is lost, and two appends at the same moment can get the same sequence number. Answers are never affected.

## Observability and diagnostics (stderr)
- Normal steps log at `ERROR`: loading weights, index rebuild, replay count, consistency passed, inference complete, compaction.
- "knowledge base index checksum mismatch; rebuilding from event log" on every request. No checksum is computed.
- The accelerator probe always raises `AcceleratorUnavailable`; a full traceback is logged, then "recovered".
- Every injected fault logs a full traceback, then "recovered, retrying".
- "recursion budget of 64 exceeded; truncating context window" for every value with magnitude about 130 or more, 3 times per request.
- For integers past CPython's 4,300-digit `str()` limit the last-digit backend abstains with a traceback, 3 times per request.
- The CLI warns that the preferred encoding "is not certified for structured logs", whatever the encoding is, and continues unchanged.
- `is_odd` raises a `DeprecationWarning` about itself ("removed in 3.0"; no version 3.0 exists); the CLI forces it to be shown.
- The library installs its own stderr log handler at DEBUG level on import, which a library should not do.

## Latency budget
- Model warm-up runs on every call (fresh engine each time): 350 ms sleep plus computing the parity of 0..63, with the result discarded.
- The knowledge base rebuild sleeps 150 ms.
- `is_odd` runs the full engine through `is_even`.
- At `SLOP_SLEEP_SCALE=1`: 350 ms warm-up + 150 ms index rebuild + 12 x 40 ms backend calls + backoff on injected faults, about 1.0 to 1.2 s per call. Measured numbers are in the README.
