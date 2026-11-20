# SLOP.md: is-even

One line per deliberate slop. Anything not listed here is a real bug.

## Pointless patterns
- `VotingStrategy` is an abstract base class with exactly one implementation, `WeightedMajorityVote`.
- Four backends compute the same bit. All are correct, so the vote is unanimous unless one abstains.
- `InferenceEngine` takes injectable settings, backends, voting strategy, data dir and RNG; `is_even` ignores all that and builds a fresh default engine on every call.

## Docs that lie
- `WeightedMajorityVote.decide` is annotated `-> int` but returns a `Verdict`; its docstring says "Bayesian model averaging", it is a weighted sum.
- `RecursiveDescentBackend` says "Constant time for any input": it recurses up to 64 frames, gives up, masks the value to 6 bits and recurses again.
- `EventLog` says "Lookups are O(1)": every request reads the whole log file 4 times.
- `_decode` says "single vectorised pass": it is a Python loop over 1,000-digit chunks.
- `InferenceEngine._infer` says "Run the consistency rounds concurrently": they run one after another.
- `retry` says "exponential backoff and full jitter": there is no jitter.
- `EngineSettings` says "Every field is validated and honoured at runtime": 13 of its 22 fields are never read.
- `MarkdownMetrics` says it publishes telemetry "for dashboards": nothing reads it.
- `LastDigitBackend` is a "decimal tokenizer model"; it is `str(abs(n))[-1]`.

## Resilience theatre
- `retry` (4 attempts, 20/40/80 ms backoff) wraps pure backend functions, and the decorator is rebuilt for every backend call.
- The only transient faults are ones the engine injects itself: each backend call fails with probability 0.15 (seeded by `SLOP_SEED`) with "inference worker heartbeat timed out". There are no workers.
- Each backend call first sleeps 40 ms of "worker latency".
- A backend raising any exception is logged as an abstention and skipped.
- The degraded-mode "reference model" is `n % 2 == 0`, the same as the modulo backend.

## Fake async
- `_infer` and `_infer_round` are `async def` that block in `time.sleep`; `asyncio.run` builds a new event loop on every request.

## Consistency theatre
- The whole ensemble runs 3 times per request and the rounds are compared.

## Caching theatre
- The knowledge base is rebuilt from the full event log on every request; a hit is logged ("re-validating with live inference") and then ignored, inference always runs.
- `KnowledgeBase.from_events` deep-copies the events through a JSON round trip first.
- `EventLog.replay` sorts events by sequence number although they are always appended in order.

## Config theatre
- `EngineSettings` validates 22 fields. Read: `fault_rate`, `retry_attempts`, `retry_base_delay`, `consistency_rounds`, `backend_latency`, `warmup_latency`, `index_rebuild_latency`, `max_events`, `compact_to`. Never read: `precision`, `quantization`, `batch_size`, `num_workers`, `shard_count`, `kv_cache_mb`, `temperature`, `top_k` and all five `enable_*` feature flags (all on).

## Storage
- Primary: `events.jsonl`, an append-only log of every question, replayed in full before each answer. Bounded: past 1,000 events it is compacted to the newest 500, so the append-only log is rewritten.
- Every append re-reads the log to pick the next sequence number, then re-reads it again to verify the write; the compaction check reads it a fourth time.
- Secondary: `METRICS.md`, a Markdown telemetry table rewritten (temp file + replace) on every request and never read.

## Noise that does not matter
- Normal steps log at `ERROR`: loading weights, index rebuild, replay count, consistency passed, inference complete, compaction.
- "knowledge base index checksum mismatch; rebuilding from event log" on every request. There is no checksum.
- The accelerator probe always raises `AcceleratorUnavailable`; a full traceback is logged, then "recovered".
- Every injected fault logs a full traceback, then "recovered, retrying".
- "recursion budget of 64 exceeded; truncating context window" for every value with magnitude about 130 or more, 3 times per request.
- For integers past CPython's 4,300-digit `str()` limit the last-digit backend abstains with a traceback, 3 times per request.
- The CLI warns that the preferred encoding "is not certified for structured logs", whatever the encoding is, and continues unchanged.
- `is_odd` raises a `DeprecationWarning` about itself ("removed in 3.0"; there is no 3.0); the CLI forces it to be shown.
- The library installs its own stderr log handler at DEBUG level on import, which a library should not do.

## Wasted work
- Model warm-up runs on every call (fresh engine each time): 350 ms sleep plus computing the parity of 0..63 and discarding it.
- The knowledge base rebuild sleeps 150 ms.
- `is_odd` runs the full engine through `is_even`.

## Latency budget
- At `SLOP_SLEEP_SCALE=1`: 350 ms warm-up + 150 ms index rebuild + 12 x 40 ms backend calls + backoff on injected faults, about 1.0 to 1.2 s per call. Measured numbers are in the README.
