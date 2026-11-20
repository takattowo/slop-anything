# Engineering ledger: left-pad

Every design decision in `ports/left-pad` that affects latency, I/O or diagnostics is recorded here, one line each. Any behaviour not recorded here is a defect. The answer is always the npm left-pad 1.3.0 result.

## Storage engine
- The memo store is a generated Python module, `<data dir>/_layout_registry.py`, holding `GENERATION` and an `ENTRIES` dict literal. It is imported with importlib before every request and rewritten after it (`registry.py`).
- After each rewrite the module is imported again as read-after-write verification (`LayoutRegistryStore.commit`).
- `importlib.invalidate_caches()` runs on every load, and bytecode caching is switched off, so the module is recompiled from source every time.
- A memo hit is verified, not trusted: it is still computed three times, so a hit saves no work (`ComposeStage`).
- Bounds: 128 entries, oldest first out; results over 2,048 characters are not memoised.
- Secondary storage: `layout_telemetry.zip` (counters and the last 100 timings) is read in full and rewritten as a new zip on every request. Only the next write consults it (`telemetry.py`).

## Architecture
- `PaddingStrategy` ABC and a `StrategyRegistry` holding a single production strategy, rebuilt on every request.
- Plugin discovery imports `leftpad.plugins.binary_doubling`, which does not exist. It runs only on requests whose number is a multiple of 11, so every 11th request logs a full `ModuleNotFoundError` / `StrategyResolutionError` traceback, waits 0.3 s, and recovers through `VendoredStrategy` (`_vendor/left_pad_1_3_0.py`, the same algorithm again).
- `LayoutPipeline` of four stages that JSON round-trips the whole context before every stage.
- `LayoutEventBus` publishes 8 events per request; no observers are registered.
- The renderer is `async def` with blocking `time.sleep`, run by `asyncio.run` on a new event loop per request; inside a running loop it drives the coroutine by hand and logs an ERROR.

## Configuration
- `LayoutSettings` has 16 fields, 8 of them validated in `__post_init__` (`encoding` by an `encode` call whose result is discarded); only `column_width` is consulted, to print a warning.
- Feature flags `vectorized_fill`, `zero_copy_render`, `adaptive_strategy`, `predictive_cache`: all on, reserved for future use; not consulted by the current code paths.

## Documentation notes
- `BinaryDoublingStrategy` is documented as O(1) with a precomputed table; it is the O(log n) doubling loop.
- `measure()` is documented as returning East Asian Width display columns and annotated `-> float`; it returns UTF-16 code units as an `int` (which is what npm needs).
- `js_length()` is annotated `-> int` and returns `None` for NaN.
- `GlyphStreamRenderer.render()` and `_stream()` are annotated `-> list[str]` and return `str`.
- `js_string()` is documented as exact ECMAScript `String()`; only str, int, bool and None follow it (floats use Python `str()`, so `1.0` is `"1.0"`, not `"1"`).
- `LayoutPipeline` is documented as lock-free and zero-copy; it copies the context five times (`dict(request)`, then a JSON round-trip before each of the four stages).
- `LayoutSettings` is documented as "applied to every layout request"; no request applies it.
- `left_pad()` warns that it is deprecated in favour of `LayoutEngine.layout()` and will be removed in leftpad 2.0; it remains fully functional, and no leftpad 2.0 exists.

## Resilience
- The pure coercion functions `js_string`, `js_length` and `js_fill` run under `@retry` with exponential backoff. In practice only an infinite length makes one fail, and it then retries a deterministic `ValueError` three times, logging each as a transient fault.

## Consistency verification
- The padding is computed 3 times and compared, with a 0.05 s pause per round.

## Observability and diagnostics (stderr only)
- Every request logs `ERROR ... layout registry index failed integrity verification; rebuilding`. No integrity check or rebuild runs; the step waits 0.25 s (±10%, seeded).
- `WARNING ... terminal width could not be determined; assuming 80 columns`; the width is not used.
- ERROR level for normal events: cache misses, successful read-after-write verification, and `completed with status OK`.
- DEBUG and INFO lines for strategy registration, shard routing and cache hits.
- The library installs its own stderr handler on the `leftpad` logger at import, at DEBUG level, with propagation off, so the root logger cannot silence it.
- The shard (0..15, seeded) is logged and archived; there is one shard.

## Latency budget (at `SLOP_SLEEP_SCALE=1`, scale clamped to 0..10)
- 0.25 s ±10% registry rebuild, 3 x 0.05 s verification, 0.3 s extra on every 11th request.
- Glyph streaming: 0.02 s per character, capped at 1.0 s per render; sleeps are batched once they reach 5 ms, so length 10,000 does about 200 sleeps, not 10,000.
- Registry write contention (another process holds `_layout_registry.py`): up to 4 backoff pauses of 0.05, 0.1, 0.2 and 0.4 s, 0.75 s in total, then the snapshot is discarded.
- Every pause above scales with `SLOP_SLEEP_SCALE` (through `config.pause()`, or `sleep_scale()` in the renderer).
- Upper bound of the latency budget per request: about 1.73 s at scale 1, or about 2.48 s when the registry write is contended.

## Hard limits
- Target length over 10,000 (or infinite) raises `ValueError`; CLI exits 2.
- Values over 100,000 characters and padding over 100,000 characters (deficit x fill length) raise `ValueError`.

## Known limits
- A length that `int()` cannot convert (`"abc"`, `None`, `"5.5"`, NaN) is treated as JavaScript NaN: the value comes back unchanged. (npm would pad for `"5.5"`; this port does not.)
- Floats are truncated by `int()` before subtraction; npm subtracts first. Both give the same result for non-negative lengths.
