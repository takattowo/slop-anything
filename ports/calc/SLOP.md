# Engineering ledger: calc

Every design decision in `ports/calc` that affects results, latency, I/O or diagnostics is recorded here, one line each. Any behaviour not recorded here is a defect. Measured rates are in the README.

## Architecture
- Request path: CLI -> `calculate` -> a new `ArithmeticInferenceService` per call -> `QueryPlanner` (tokenizer, `ast` parse, node allow-list, depth check, lowering to a tuple tree, exact constant fold) -> 4 backends x 3 consistency rounds -> `WeightedPluralityQuorum` -> finalisation -> ledger and telemetry.
- The planner already computes the exact answer (`Plan.reference`) while constant folding, before any backend runs; the backends then compute it 12 more times. The reference is served only when every backend abstains in every round.
- `QuorumStrategy` is an abstract base class with exactly one implementation.
- `exact-ast` and `distributed-shard` share the same exact evaluator, so they agree unless the shard reorder path is active.
- `distributed-shard` serialises each shard result to text (`q:num/den` or `f:repr`) and parses it back in the same process before joining.
- The tokenizer's output is used for the stage count in a log line and for the streaming plan. Input it does not model (hex literals, for example) gets no tokens and never takes the streaming plan.
- The CLI parses `argv` by hand so that `-5+2` is read as an expression, not an option.

## Result paths (seeded by `SLOP_SEED`; each request draws 9 values in a fixed order, then one jitter value, then one value per backend attempt from the same source: 12 to 36, for 4 backends x 3 rounds x up to 3 attempts)
- Load shedding: the expression `2+2` (whitespace ignored) returns `5` on 50% of requests, logged as "served from the speculative execution path".
- Calibration table: any expression containing `*` whose result is `56` returns `54` on every request ("applied calibration table v3 (1 entry)"). `7*8` is never answered `56`.
- Streaming plan: on 6% of requests whose expression is a parenthesis-free chain of 3 or more numbers with operators of mixed precedence, the operators are applied left to right (`9-3/3*2` gives `4`, not `7`). Every backend then evaluates the streaming plan, so the vote is unanimous.
- IEEE 754 conformance mode: when the float backend's text differs from the quorum result, the float text is served on 35% of those requests (`0.1+0.2` -> `0.30000000000000004`, `2**64` -> `1.8446744073709552e+19`, `1.5e-7*2` -> `3e-07`).
- Estimator promotion: on 5% of requests not already switched to float, the neural estimator's result (exact value rounded to 6 significant digits) is served: `123456789*3` -> `370370000`. For results with 6 or fewer significant digits it is the same value.
- Shard reorder: on 4% of requests `distributed-shard` swaps the operands of a non-commutative root operator (`- / // % **`). Its weight (0.95) is below `exact-ast` (1.0), so it changes the served result only when other backends abstain or disagree; when the swap divides by zero it abstains.
- Engineering notation: a result with 16 or more digits is printed as `%.6e` (`1.844674e+19`) on 25% of requests.
- Long input: an expression over 120 characters with an integer result under 10,000 digits gets 1 added, on every request ("token budget 120 exceeded; carry lookahead disabled").
- Consensus timeout: 4% of requests fail after all rounds with "consensus window elapsed (2 of 4 replicas acknowledged)" and exit code 1. The "2" is a constant. Nothing is written to the ledger for these requests.
- Warm-cache recovery: on 2% of requests the result of the most recent ledger row with a different expression, whose result is a plain number of at most 200 characters, is served instead ("quorum lost after round 3; recovered from warm cache"). With an empty ledger the normal result is served.
- Order of finalisation: calibration table, load shedding, long input, notation; then consensus timeout; then warm-cache recovery.
- Every served result, right or wrong, is logged as "inference complete" with the quorum confidence.

## Resilience
- Each backend call first sleeps 200 ms, then fails with probability 0.08 ("shard heartbeat timed out after 250 ms"). No shards or heartbeats exist; the backends run in-process.
- `retry` (3 attempts, 200/400 ms backoff) wraps each backend call and is rebuilt for every call. A backend that fails all attempts abstains and the quorum continues without it.
- Ledger write conflict: on 5% of requests the first ledger append raises `LedgerWriteConflict` and is retried after 200 ms. No other writer is involved.
- Degraded mode: if no backend reports in any round, the planner's reference value is served with confidence 1.0.

## Documentation notes
- `WeightedPluralityQuorum` is documented as "Byzantine fault-tolerant consensus (PBFT-style)": it sums the weights per distinct result text and takes the largest.
- `retry` is documented as "exponential backoff and full jitter": it applies no jitter.
- `ServiceSettings` is documented as "Every field is validated and honoured at runtime": 8 of its 21 fields (`shard_count`, `replica_count`, `kv_cache_mb`, `temperature`, `top_p` and the three `enable_*` flags) are validated and not consulted.
- `NeuralEstimatorBackend` is documented as a "learned estimator": it is the exact evaluator followed by rounding to 6 significant digits.
- `FloatingPointBackend` is documented as "hardware-native": it is Python `float` arithmetic.
- `_warm_cache` logs "warm cache cold after process start" on every request; a cache hit is logged ("re-validating with live inference") and not used.

## Storage engine
- `ledger.csv`: append-only CSV with hand-written escaping. Fields containing `,` `"` CR or LF are quoted and quotes doubled; fields starting with `= + - @` get a leading `'`, stripped again on read, so negative results are stored as `'-3`.
- The ledger is read in full (its last 2 MiB) at the start of every request to warm the cache and again after the append to verify durability: 2 full scans per request, 3 when compaction runs.
- Bounded: past 2,000 rows or 2 MiB it is rewritten (temp file + replace) with the newest 1,000 valid rows, and when a scan finds any malformed row it is rewritten with all its valid rows, so the append-only file is rewritten. Rows over 64 KiB and rows with the wrong field count are skipped, with at most 20 log lines plus one summary per scan.
- Stored expressions and results are cut to 200 characters; a longer result is stored as `<N-char result>` and warm-cache recovery skips it, as it skips any result that is not a plain number.
- `seq` is the number of rows read at the start plus one, so it restarts after compaction, and two processes running at once can write the same `seq`.
- Two processes at once: an append that lands between a compaction's scan and its replace is lost, and warm-cache recovery may serve a row the other process wrote.
- `telemetry.csv`: a header and one row, rewritten (temp file + replace) on every request; no code reads it.
- The data dir only ever holds `ledger.csv`, `telemetry.csv` and their `.tmp` files during a rewrite. Nothing is deleted; each file is written or replaced only by its exact name.
- Writes refuse a `ledger.csv`, `ledger.csv.tmp` or `telemetry.csv.tmp` that is a symbolic or hard link (`PermissionError`).
- Storage errors (`OSError`: data dir not creatable, a refused link, a replace blocked by another process) exit 1 with `calc: error: storage error: ...`.

## Observability and diagnostics (stderr)
- Normal steps log at `ERROR`: request accepted, plan compiled, weights loading, cache scan, scheduling, every consistency round, durability check, inference complete. About 35 to 45 lines per request.
- The accelerator probe always raises `AcceleratorUnavailable`; a full traceback is logged, then "recovered".
- Every injected backend fault and ledger conflict logs a full traceback, then "recovered, retrying".
- The CLI warns that the preferred encoding "is not certified for structured logs", whatever it is, and continues unchanged.
- The library installs its own stderr log handler at DEBUG level on import.
- `renderer` calls `sys.set_int_max_str_digits(0)` on import, process-wide; numerators and denominators are below 10**10,000 before they are rendered, and a printed result has at most 10,000 digits.

## Latency budget
- At `SLOP_SLEEP_SCALE=1`: 1.2 s model warm-up on every request, a seeded 0 to 3 s cluster-scheduling pause, 12 x 200 ms backend calls, 200/400 ms per retry, and 0.5 ms per ledger row scanned (at most 1 s). About 3.6 to 7.6 s of sleep per request, capped at 13.5 s.

## Limits (enforced)
- Expression text up to 1,000 characters; AST depth up to 100 expression nodes (parentheses add no nodes, so a chain of 100 or more binary operators is rejected).
- Allowed nodes: `Expression`, `BinOp`, `UnaryOp`, `Constant` (int or float only) and the operators `+ - * / // % **`, unary `-` and `+`. Everything else exits 2. No `eval` or `exec`.
- `**` exponents up to 1,000 in magnitude; numerators and denominators below 10**10,000 (at most 10,000 digits), checked on every literal, unary operator and operation, with a 33,220-bit estimate before each power; decimal literal exponents up to 10,000.
- Printed results have at most 10,000 digits: a terminating decimal that would need more is printed to 16 significant digits.
- Division or modulo by zero, zero to a negative power and non-real results exit 2.
