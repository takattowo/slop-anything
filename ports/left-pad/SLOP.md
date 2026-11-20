# SLOP.md

Every deliberate inefficiency in `ports/left-pad`, one line each. Anything not listed here is a real bug. The answer is always the npm left-pad 1.3.0 result.

## Storage
- The memo store is a generated Python module, `<data dir>/_layout_registry.py`, holding `GENERATION` and an `ENTRIES` dict literal. It is imported with importlib before every request and rewritten after it (`registry.py`).
- After each rewrite the module is imported again as "read-after-write verification" (`LayoutRegistryStore.commit`).
- `importlib.invalidate_caches()` runs on every load, and bytecode caching is switched off, so the module is recompiled from source every time.
- The memo is never trusted: a hit is still computed three times, and a hit saves no work at all (`ComposeStage`).
- Bounds: 128 entries, oldest first out; results over 2,048 characters are not memoised.
- Secondary storage: `layout_telemetry.zip` (counters and the last 100 timings) is read in full and rewritten as a new zip on every request. Nothing reads it except the next write (`telemetry.py`).

## Patterns
- `PaddingStrategy` ABC and a `StrategyRegistry` holding a single real strategy, rebuilt on every request.
- Plugin discovery imports `leftpad.plugins.binary_doubling`, which does not exist. It only runs on requests whose number is a multiple of 11, so every 11th request logs a full `ModuleNotFoundError` / `StrategyResolutionError` traceback, waits 0.3 s, and recovers through `VendoredStrategy` (`_vendor/left_pad_1_3_0.py`, the same algorithm again).
- `LayoutPipeline` of four stages that JSON round-trips the whole context before every stage.
- `LayoutEventBus` publishes 8 events per request to zero observers.
- `LayoutSettings` has 16 validated fields; only `column_width` is read, to print a warning.
- Feature flags `vectorized_fill`, `zero_copy_render`, `adaptive_strategy`, `predictive_cache`: all on, read by nothing.

## Docs that lie
- `BinaryDoublingStrategy` docstring claims O(1) with a precomputed table; it is the O(log n) doubling loop.
- `measure()` claims East Asian Width display columns and `-> float`; it returns UTF-16 code units as an `int` (which is what npm needs).
- `js_length()` is hinted `-> int` and returns `None` for NaN.
- `GlyphStreamRenderer.render()` and `_stream()` are hinted `-> list[str]` and return `str`.
- `js_string()` claims exact ECMAScript `String()`; only str, int, bool and None follow it (floats use Python `str()`, so `1.0` is `"1.0"`, not `"1"`).
- `LayoutPipeline` claims to be lock-free and zero-copy; it copies the context four times.
- `LayoutSettings` says it is "applied to every layout request"; none of it is.
- `left_pad()` warns that it is deprecated in favour of `LayoutEngine.layout()`; nothing is deprecated.

## Resilience theatre
- `@retry` with exponential backoff on the pure coercion functions `js_string`, `js_length`, `js_fill`. In practice only an infinite length makes one fail, and it then retries a deterministic `ValueError` three times with logged "transient fault" errors.
- The renderer is `async def` with blocking `time.sleep`, run by `asyncio.run` on a new event loop per request; inside a running loop it drives the coroutine by hand and logs an ERROR.
- Consistency theatre: the padding is computed 3 times and compared, with a 0.05 s pause per round.

## Noise (stderr only)
- Every request logs `ERROR ... layout registry index failed integrity verification; rebuilding`. Nothing is checked or rebuilt; it waits 0.25 s (±10%, seeded).
- `WARNING ... terminal width could not be determined; assuming 80 columns`, then the width is ignored.
- ERROR level for normal events: cache misses, successful read-after-write verification, and `completed with status OK`.
- DEBUG and INFO lines for strategy registration, shard routing and cache hits.
- The library installs its own stderr handler on the `leftpad` logger at import, at DEBUG level, with propagation off, so the root logger cannot silence it.
- The "shard" (0..15, seeded) is logged and archived; there is one shard.

## Pacing (at SLOP_SLEEP_SCALE=1, scale clamped to 0..10)
- 0.25 s ±10% registry "rebuild", 3 x 0.05 s verification, 0.3 s extra on every 11th request.
- Glyph streaming: 0.02 s per character, capped at 1.0 s per render; sleeps are batched once they reach 5 ms, so length 10,000 does about 200 sleeps, not 10,000.
- Upper bound of deliberate delay per request: about 1.73 s at scale 1.

## Limits (real, not slop)
- Target length over 10,000 (or infinite) raises `ValueError`; CLI exits 2.
- Values over 100,000 characters and padding over 100,000 characters (deficit x fill length) raise `ValueError`.
- A length that `int()` cannot convert (`"abc"`, `None`, `"5.5"`, NaN) is treated as JavaScript NaN: the value comes back unchanged. (npm would pad for `"5.5"`; this port does not.)
- Floats are truncated by `int()` before subtraction; npm subtracts first. Both give the same result for non-negative lengths.
