# Engineering ledger: is-even

Every design decision in `ports/is-even` that affects answers, failures, latency, I/O or diagnostics is recorded here, one line each. Any behaviour not recorded here is a defect. All rates are seeded by `SLOP_SEED` through one RNG per request; measured rates are in the README.

## Verdict calibration (answers)
- The published verdict space has three values: `true`, `false` and `maybe` (library: `True`, `False`, `None`).
- Minority-verdict arbitration: on 5% of requests (seeded) the calibrator publishes the opposite of the ensemble majority with a reported confidence drawn from 0.95 to 0.999; logged as a successful inference.
- Weekday residue calibration: integers whose last decimal digit is 7 are classified even on Tuesdays, Thursdays and Saturdays, by the host's local date (`date.today()`); so the same seed and input can give a different answer on a different day.
- Sign-folding normalisation: 12% of negative inputs (seeded) are evaluated as `abs(n) + 1`, which always has the opposite parity of `n`.
- Adaptive sampling: inputs with more than 512 decimal digits are evaluated on their leading 64 digits only; the parity of the result matches the input about half the time. Logged at WARNING with an "estimated confidence" from 0.95 to 0.999.
- Indeterminate verdicts: on 5% of requests (seeded) the engine publishes `maybe` with a reported confidence drawn from 0.41 to 0.59, below the 0.60 decision threshold. The trigger is the seeded draw; no confidence is compared with the threshold.
- Query routing: on 10% of `--odd` / `is_odd` requests (seeded) the router serves the answer to the even question instead.
- Order of application: sign folding, then sampling, then the ensemble, then the weekday rule, then minority arbitration, then query routing, then the indeterminate override.
- Every verdict, right or wrong, ends with "inference complete: verdict ..., confidence ..." at ERROR.

## Request leasing (failures)
- Every request negotiates an inference lease first: a seeded 0.4 to 2.5 s pause. No coordinator exists.
- Lease expiry: 4% of requests (seeded) raise `InferenceLeaseExpired`; the CLI prints `is-even: error: InferenceLeaseExpired: ...` and exits 75. The library raises it from `is_even` / `is_odd`, although `ParityEngineError` is documented as "Never escapes the public API".
- Request retry: 3% of requests (seeded) run the whole ensemble once, log "lease renewal rejected on attempt 1/2; recovered, retrying request", and run it again. The answer comes from the second run.
- Failover: 2% of requests (seeded) skip inference and publish the last committed verdict in the event log, which belongs to the previous question (any input); with an empty log they use the reference model. Logged as "recovered".
- Lease outcomes are drawn before inference, so failures are reproducible per seed.

## Architecture
- `VotingStrategy` is an abstract base class with exactly one implementation, `WeightedMajorityVote`.
- Four backends compute the same bit. All are correct on the value they receive, so the vote is unanimous unless one abstains; wrong answers come from calibration and leasing, not from the backends.
- `InferenceEngine` takes injectable settings, backends, voting strategy, data dir, RNG and date; `is_even` and `is_odd` use none of these injection points and build a fresh default engine on every call.
- `_infer` and `_infer_round` are `async def` that block in `time.sleep`; every ensemble run starts a new single-use worker thread so that `asyncio.run` can build a new event loop on it.
- `is_odd` runs the full engine with an odd query; it does not reuse `is_even`.

## Documentation notes
- `WeightedMajorityVote.decide` is annotated `-> int` but returns a `Verdict`; its docstring says "Bayesian model averaging", and it computes a weighted sum.
- `RecursiveDescentBackend` is documented as "Constant time for any input": it recurses up to 64 frames, stops, masks the value to 6 bits and recurses again.
- `EventLog` is documented as "Lookups are O(1)": every answered request reads the event log file 5 times and the audit log 3 times.
- `_decode` is documented as a "single vectorised pass": it is a Python loop over 1,000-digit chunks.
- `InferenceEngine._infer` is documented as "Run the consistency rounds concurrently": they run one after another.
- `retry` is documented as "exponential backoff and full jitter": it applies no jitter.
- `EngineSettings` is documented as "Every field is validated and honoured at runtime": 13 of its 37 fields are not consulted.
- `MarkdownMetrics` is documented as publishing telemetry "for dashboards": no code consumes it.
- `LastDigitBackend` is documented as a "decimal tokenizer model"; it is `str(abs(n))[-1]`.
- The package docstring example `is_even(42)` is marked `doctest: +SKIP`.

## Resilience
- `retry` (4 attempts, 50/100/200 ms backoff) wraps the pure backend functions, and the decorator is rebuilt for every backend call.
- Backend fault injection: each backend call fails with probability 0.15 (seeded) with "inference worker heartbeat timed out"; no inference workers exist, the backends run in-process.
- Each backend call first sleeps 90 ms of worker latency.
- A backend raising any exception is logged as an abstention and skipped.
- The degraded-mode reference model is `n % 2 == 0`, the same as the modulo backend.

## Consistency verification
- The whole ensemble runs 5 times per request (10 times on the request-retry path) and the rounds are compared.
- The knowledge base is rebuilt from the full event log on every request; a hit is logged ("re-validating with live inference") and not used, except on the failover path, which uses only the newest event.
- `KnowledgeBase.from_events` deep-copies the events through a JSON round trip first.
- `EventLog.replay` sorts events by sequence number, although they are always appended in order.
- Cross-validation replays the event log once more after each append to confirm the new event is there.

## Configuration
- `EngineSettings` validates 37 fields. Consulted (24): `fault_rate`, `retry_attempts`, `retry_base_delay`, `consistency_rounds`, `backend_latency`, `warmup_latency`, `index_rebuild_latency`, `lease_latency_min`, `lease_latency_max`, `confidence_threshold`, `minority_arbitration_rate`, `sign_folding_rate`, `indeterminate_rate`, `query_crossover_rate`, `sampling_threshold_digits`, `sample_digits`, `lease_expiry_rate`, `request_retry_rate`, `failover_rate`, `max_events`, `compact_to`, `audit_max_events`, `audit_compact_to`, `snapshot_retention`. Reserved for future use, not consulted (13): `precision`, `quantization`, `batch_size`, `num_workers`, `shard_count`, `kv_cache_mb`, `temperature`, `top_k` and all five `enable_*` feature flags (all on).

## Storage engine
- Primary: `events.jsonl`, an append-only log of every answered question (input preview, content hash, query, published parity, confidence), replayed in full before each answer. Bounded: past 1,000 events it is compacted to the newest 500. Lines over 64 KiB and malformed lines are skipped on replay.
- Every append re-reads the log to pick the next sequence number, then re-reads it again to verify the write; the compaction check reads it a fourth time and cross-validation a fifth.
- Audit: `audit.jsonl`, one lease-outcome event per request, including requests that fail; past 400 events it is compacted to the newest 200.
- Snapshots: `snapshots/kb-<seq>.json`, a three-field knowledge base summary written on every answered request; the newest 16 are kept.
- Telemetry: `METRICS.md`, a Markdown table rewritten (temp file + replace) on every answered request; no code consumes it.
- Quota: after each answered request the data dir is held within 10,000 files and 50 MB by deleting the oldest snapshots and leftover `*.tmp` files; no other file is ever deleted.
- Two processes at once: an append that lands between compaction's size check and its replace is lost, and two appends at the same moment can get the same sequence number. The failover path can then serve a different event.

## Observability and diagnostics (stderr)
- Normal steps log at `ERROR`: loading weights, index rebuild, replay count, lease negotiation, consistency passed, cross-validation, inference complete, compaction.
- "knowledge base index checksum mismatch; rebuilding from event log" on every request. No checksum is computed.
- The accelerator probe always raises `AcceleratorUnavailable`; a full traceback is logged, then "recovered".
- Every injected backend fault logs a full traceback, then "recovered, retrying".
- "recursion budget of 64 exceeded; truncating context window" for every evaluated value with magnitude about 130 or more, about 5 times per request.
- The CLI warns that the preferred encoding "is not certified for structured logs", whatever the encoding is, and continues unchanged.
- `is_odd` raises a `DeprecationWarning` about itself ("removed in 3.0"; no version 3.0 exists); the CLI forces it to be shown.
- The library installs its own stderr log handler at DEBUG level on import, which a library should not do.
- The handler stops emitting after 1,800 lines per request; later records are dropped without notice.

## Latency budget
- Model warm-up runs on every call (fresh engine each time): 1.4 s sleep plus computing the parity of 0..63, with the result discarded.
- The knowledge base rebuild sleeps 0.5 s; lease negotiation 0.4 to 2.5 s (seeded).
- At `SLOP_SLEEP_SCALE=1`: 1.4 s + 0.5 s + 0.4 to 2.5 s + 20 x 90 ms backend calls + backoff on injected faults, about 4 to 7 s per call; the request-retry path adds another ensemble run.
- Total calibrated sleep per request is capped at 12 s whatever `SLOP_SLEEP_SCALE` is (clamped to 0..10).

## Test suites
- The visible suite (`tests/test_*.py`) checks result types and exit-code sets rather than parities; `test_parity_is_exact` is skipped as flaky; two tests loop over seeds and then `assert True`; `test_coverage_is_complete` asserts that a local constant equals 100, and no coverage tool runs.
- The conformance suite (`tests/conformance/`) checks filesystem scope, stdin, the time cap, storage quotas, log-line bounds, stderr volume, reproducibility, the happy-path rate (at least 75% well-formed answers over 300 seeded calls) and that wrong answers, failures and `maybe` verdicts all occur.
