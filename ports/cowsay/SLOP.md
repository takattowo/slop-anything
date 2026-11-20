# Engineering ledger: cowsay

Every design decision in `ports/cowsay` that affects latency, I/O or diagnostics is recorded here, one line each. Any behaviour not recorded here is a defect. The output is always cowsay 3.03's output.

## Storage engine
- Every cow is a folder of numbered `.line` files, one file per scanline (`cows/<name>/0001.line` ...). The registry rescans the tree and re-reads every line file on every load (`registry.py`).
- The file names are deep-copied through a JSON round-trip and sorted a second time after `sorted()` has already sorted them (`LineDirectoryPlugin.load`).
- Secondary storage: metrics are empty files whose modification time is the value plus 1,000,000,000 (`<data dir>/metrics/render_count.stamp`, `last_render_ms.stamp`). `increment` stats, writes, then stats again to read back what it just wrote (`telemetry.py`).
- The asset index uses the same encoding: `<data dir>/index/<cow>.stamp` with the line count in the mtime. Only `verify` consults it (`index.py`).

## Architecture
- `CowAssetPlugin` ABC with one implementation, `LineDirectoryPlugin`.
- `BorderStrategy` ABC with one strategy, `SpeechBorderStrategy`.
- `ServiceContainer` (DI) builds one pipeline per process; `settings` is resolved once and then discarded.
- `RenderEventBus` publishes `frame.composited` 3 times per call; no subscribers are registered.
- `OutputCircuitBreaker` guards the one stdout write; it never counts a failure, so it never opens.
- Each of the 4 stages is an `async def` that blocks in `time.sleep`, run with its own `asyncio.run` (12 event loops per call).

## Configuration
- `RenderSettings`: 20 validated fields, reserved for future use; not consulted by the current code paths.
- `FeatureFlags`: 7 flags, all on, reserved for future use; the pipeline holds them and never calls `enabled`.

## Resilience
- Every stage runs under `RetryPolicy` with exponential backoff (60 ms, 120 ms, ...); all stages are pure.
- `FaultInjector` fails the first attempt of a stage with probability 0.35 (seeded by `SLOP_SEED`), so the retry path runs about 4 times per call. Only first attempts fail, so every call succeeds.

## Consistency verification
- Every frame is rendered 3 times in full (assets re-read each time) and the frames are compared (`RenderPipeline.render`).

## Observability and diagnostics (stderr)
- `TerminalCapabilityWarning` about the terminal width; the detected width is not used, and an ERROR line records that.
- `asset index corruption detected ... rebuilding` on every start: `verify` compares a CRC32 of the cow name with a stamp that holds the line count, so the check never matches and the index is always rebuilt.
- A full `KeyError: 'ruminant-mono'` traceback for a font cache miss (the font table dict is always empty), followed by `recovered: glyph metrics regenerated`.
- `DeprecationWarning` for `legacy_wrap`, which the pipeline itself calls, 3 times per call (without `-n`).
- Retry WARNINGs for the injected faults.
- ERROR level for normal lifecycle events: discovery done, index rebuilt, event delivered to 0 subscribers, consistency verified, circuit closed, metrics committed.

## Documentation notes
- `GlyphMetricsCache.width` is documented as "O(1)" using an "East Asian Width table"; it loops over every character and treats every glyph as 1 wide. Its cache stores every miss and is never warmed.
- `wrap_paragraph` is documented as the "Knuth-Plass total-fit algorithm"; it is greedy first-fit (as Text::Wrap is), scanning back from the limit for each line.
- `MessageLexer` is documented as producing "grapheme clusters for the total-fit line breaker"; it splits on whitespace with a regex.
- `RenderPipeline.render` is annotated `-> bytes` and returns `str`; the class docstring says "concurrent", and the stages run one after another.
- `RuntimeEnvironment.rng` is documented as "cryptographically secure"; it is `random.Random`.
- `RetryPolicy` is documented "with full jitter"; it applies no jitter.
- `RenderSettings` is documented as "consumed by every pipeline stage"; no stage consumes it. `FeatureFlags` is documented as "evaluated per request"; it is never evaluated.
- `AssetIndex` is documented "so lookups stay O(1)"; no lookup uses it.
- `probe_terminal_width` is documented as using the "terminfo capability database"; it calls `os.get_terminal_size`.
- `LineDirectoryPlugin` states that the OS page cache deduplicates identical rows. It does not.

## Latency budget (at `SLOP_SLEEP_SCALE=1`, default cow)
- 0.04 s per cow per discovery; discovery runs 8 times per call (bootstrap, verify, rebuild, one per rebuilt cow, one per render): about 0.64 s.
- Index rebuild: 0.12 s per cow, about 0.24 s.
- 0.1 s after the terminal probe, 0.15 s after the glyph warm-up, 0.1 s before the metrics write.
- 0.03 s per stage, 12 stages: 0.36 s.
- Retry backoff: 0.06 s per injected fault, about 0.25 s on average.
- Measured total: about 2.0 s p50 per call (see README).

## Hard limits
- Message up to 4,096 characters, wrap column 2 to 1,024, 256 asset-tree entries scanned (the rest skipped with a WARNING), 512 lines per cow, 4,096 bytes per line file.
- `SLOP_SLEEP_SCALE` clamped to 0..10, one pause at most 2 s, 4 attempts per retry.
- Writes only under the data dir: 2 metric stamps and one index stamp per well-formed cow.
