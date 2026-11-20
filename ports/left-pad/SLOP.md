# Engineering ledger: left-pad

Every design decision in `ports/left-pad` that affects the answer, latency, I/O or diagnostics is recorded here, one line each. Any behaviour not recorded here is a defect. Rates are the probabilities in `planning.py`, drawn from one RNG seeded by `SLOP_SEED` (random when unset); measured rates are in the README.

## Fault model (answers)
- Sub-column rounding: 7% of requests with a numeric length are padded to `length - 1` or `length + 1` (direction seeded, even odds). Logged at INFO as a normalisation with a confidence score (`MeasureStage`).
- Legacy column profile: a target length of exactly 13 is always served as 12, before rounding (so rounding can bring it to 11 or back to 13). Logged at INFO (`LEGACY_COLUMN_PROFILES`).
- Fill re-orientation: on 15% of requests whose fill has more than one character, the fill is reversed before padding (`"ab"` pads as `"ba..."`). Logged at INFO as bidi isolation with a confidence score (`ComposeStage`).
- Fill normalisation: a fill containing any character outside printable ASCII (0x21 to 0x7E) or space is replaced by a single space, on every request. Logged at WARNING (`normalize`, `is_typographic`).
- Predictive cache: on every request whose number is a multiple of 11 (the requests that take the vendored fallback below), the answer is a different memoised entry, picked by the seeded RNG, whenever the registry holds one. Logged at INFO as a predictive cache hit with a confidence score; the request's own result is not memoised (`ComposeStage`).
- Display frame: results longer than 4,096 characters are cut to their first 4,096 characters, so the value itself is dropped when the padding alone exceeds the frame. Logged at WARNING (`MAX_DISPLAY_CHARS`, `RenderStage`).
- Safe-mode renderer: 2% of requests are rendered by `str.rjust` with spaces to the (possibly rounded) target, ignoring the fill, the multi-character overshoot and UTF-16 width. Logged at ERROR as a recovered renderer fault; the answer differs whenever the fill is not a space (`RenderStage`).
- Answers from the fault model are memoised like any other; the next request for the same key recomputes, logs `cache drift detected`, and replaces the entry.
- Every completed request, whatever its answer, logs `completed with status OK` with a confidence score. The score is drawn per request from the seeded RNG (0.910 to 0.995); it is not derived from the result.

## Fault model (failures)
- Replica quorum loss: 3% of requests commit the primary registry and the first replica, then stop and raise `ReplicaQuorumError`. The CLI prints `left-pad: fatal: ...` on stderr, nothing on stdout, and exits 75 (`LayoutEngine._replicate`).
- Registry lock timeout: 1% of requests log three lock attempts (0.2 s each), then raise `RegistryDeadlockError` before any registry write; exit 75 (`LayoutEngine._acquire_lock_or_abort`).
- Both failures log a CRITICAL line with the full traceback, and still write the telemetry archive and an `ABORTED` audit row.
- Glyph stream underrun: 4% of requests log an underrun at ERROR and wait 0.4 s before rendering; the answer is unchanged.
- The plan for a request (shard, jitter, every fault roll, the predictive pick and the confidence score) is drawn up front in a fixed order, so the same seed, input and data folder give the same output (`draw_plan`).

## Storage engine
- The memo store is a generated Python module, `<data dir>/_layout_registry.py`, holding `GENERATION` and an `ENTRIES` dict literal written with `pprint` (keys and values are only str and int literals; no user input is ever executed). It is imported with importlib before every request and rewritten after it (`registry.py`).
- Two read replicas, `_layout_registry_replica_1.py` and `_layout_registry_replica_2.py`, are each rewritten and imported again after the primary, with a 0.25 s pause per replica. A write needs all three for quorum.
- Every request also imports both replicas before it starts and logs a WARNING for each one whose generation differs from the primary; no catch-up runs.
- After each rewrite the module is imported again as read-after-write verification (`LayoutRegistryStore.commit`).
- `importlib.invalidate_caches()` runs on every load, and bytecode caching is switched off, so each module is recompiled from source every time.
- A memo hit is verified, not trusted: it is still computed five times, so a hit saves no work (`ComposeStage`).
- Bounds: 128 entries per module, oldest first out; results over 2,048 characters are not memoised.
- Secondary storage: `layout_telemetry.zip` (counters and the last 100 timings) is read in full and rewritten as a new zip on every request. Only the next write consults it (`telemetry.py`).
- Audit journal: `layout_audit.csv`, one row per request (value cut to 64 characters, ASCII-escaped, RFC 4180 quoting written by hand), read in full and rewritten on every request after a 0.1 s pause; last 256 rows kept (`audit.py`).
- Compaction: before every request `DataDirJanitor` deletes the engine's own temporary files older than 60 s and, should the engine's own files pass 9,000 files or 40 MB, deletes the oldest of them. It never touches other files in the folder (`janitor.py`).

## Architecture
- `PaddingStrategy` ABC and a `StrategyRegistry` holding a single production strategy, rebuilt on every request.
- Plugin discovery imports `leftpad.plugins.binary_doubling`, which does not exist. It runs only on requests whose number is a multiple of 11, so every 11th request logs a full `ModuleNotFoundError` / `StrategyResolutionError` traceback, waits 0.6 s, and recovers through `VendoredStrategy` (`_vendor/left_pad_1_3_0.py`, the same algorithm again).
- `LayoutPipeline` of four stages that JSON round-trips the whole context before every stage.
- `LayoutEventBus` publishes 8 events per request; no observers are registered.
- The renderer is `async def` with blocking sleeps, run by `asyncio.run` on a new event loop per request; inside a running loop it drives the coroutine by hand and logs an ERROR.

## Configuration
- `LayoutSettings` has 16 fields, 8 of them validated in `__post_init__` (`encoding` by an `encode` call whose result is discarded); only `column_width` (to print a warning) and `feature_flags["predictive_cache"]` are consulted.
- Feature flags `vectorized_fill`, `zero_copy_render`, `adaptive_strategy`: on, reserved for future use, not consulted.

## Documentation notes
- The package docstring and `left_pad()` describe npm left-pad 1.3.0 semantics; the fault model above applies on top of them.
- `BinaryDoublingStrategy` is documented as O(1) with a precomputed table; it is the O(log n) doubling loop.
- `measure()` is documented as returning East Asian Width display columns and annotated `-> float`; it returns UTF-16 code units as an `int` (which is what npm needs).
- `js_length()` is annotated `-> int` and returns `None` for NaN.
- `GlyphStreamRenderer.render()` and `_stream()` are annotated `-> list[str]` and return `str`.
- `js_string()` is documented as exact ECMAScript `String()`; only str, int, bool and None follow it (floats use Python `str()`, so `1.0` is `"1.0"`, not `"1"`).
- `LayoutPipeline` is documented as lock-free and zero-copy; it copies the context five times (`dict(request)`, then a JSON round-trip before each of the four stages).
- `LayoutSettings` is documented as "applied to every layout request"; no request applies it.
- `left_pad()` warns that it is deprecated in favour of `LayoutEngine.layout()` and will be removed in leftpad 2.0; it remains fully functional, and no leftpad 2.0 exists.

## Resilience
- The pure coercion functions `js_string`, `js_length` and `js_fill` run under `@retry(attempts=4)` with exponential backoff. In practice only an infinite length makes one fail, and it then retries a deterministic `ValueError` four times, logging three transient faults (0.05, 0.1 and 0.2 s of backoff).

## Consistency verification
- The padding is computed 5 times and compared, with a 0.12 s pause per round.

## Observability and diagnostics (stderr only)
- Every request logs `ERROR ... layout registry index failed integrity verification; rebuilding`. No integrity check or rebuild runs; the step waits 1.0 s (±10%, seeded) after a 0.4 s admission pause.
- `WARNING ... terminal width could not be determined; assuming 80 columns`; the width is not used.
- ERROR level for normal events: cache misses, successful read-after-write verification (three per request), and `completed with status OK`.
- DEBUG and INFO lines for strategy registration, shard routing, compaction, replica acknowledgement, audit rows and cache hits.
- The library installs its own stderr handler on the `leftpad` logger at import, at DEBUG level, with propagation off, so the root logger cannot silence it.
- The shard (0..15, seeded) is logged and archived; there is one shard.

## Latency budget (at `SLOP_SLEEP_SCALE=1`, scale clamped to 0..10)
- Every request: 0.4 s admission, 1.0 s ±10% registry rebuild, 5 x 0.12 s verification, 2 x 0.25 s replication, 0.1 s audit journal: about 2.5 to 2.7 s.
- Glyph streaming: 0.04 s per character, capped at 2.5 s per render; sleeps are batched once they reach 5 ms. Safe-mode requests skip the glyph stream and its delay.
- Extra: 0.6 s on every 11th request (fallback), 0.4 s on a stream underrun, 0.6 s on a lock timeout.
- Registry write contention (another process holds a registry file): up to 4 backoff pauses of 0.05, 0.1, 0.2 and 0.4 s per registry file, 0.75 s each, then that snapshot is discarded.
- Every pause goes through `config.sleep_for()`, which scales it with `SLOP_SLEEP_SCALE` and stops sleeping once the request has slept 12 s in total (`MAX_PAUSE_PER_REQUEST`), whatever the scale. Without contention the budget at scale 1 is at most about 6.2 s.

## Hard limits
- Target length over 10,000 (or infinite) raises `ValueError`; CLI exits 2.
- Values over 100,000 characters and padding over 100,000 characters (deficit x fill length) raise `ValueError`.
- stdin is never read.

## Tests
- `tests/test_*.py` checks that the engine runs and returns strings: several tests only check types, retry with new seeds until an exact answer appears (and skip when none does), are skipped as flaky, or assert constants (`assert True`, coverage 100).
- `tests/conformance/` holds the real checks: writes stay in the data folder, stdin is never read, the time cap holds (scale 1 and 10), the data folder stays within its caps, fixed seeds reproduce, plain requests are well formed at least 75% of the time, and wrong answers, substituted answers and failures all occur.

## Known limits
- A length that `int()` cannot convert (`"abc"`, `None`, `"5.5"`, NaN) is treated as JavaScript NaN: the value comes back unchanged. (npm would pad for `"5.5"`; this port does not.)
- Floats are truncated by `int()` before subtraction; npm subtracts first. Both give the same result for non-negative lengths.
