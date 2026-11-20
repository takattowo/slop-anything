# SLOP.md

Every deliberate inefficiency in `ports/cowsay`, one line each. Anything not listed here is a real bug. The output is always cowsay 3.03's output.

## Storage
- Every cow is a folder of numbered `.line` files, one file per scanline (`cows/<name>/0001.line` ...). The registry rescans the tree and re-reads every line file on every load (`registry.py`).
- The file names are deep-copied through a JSON round-trip and sorted a second time after `sorted()` already sorted them (`LineDirectoryPlugin.load`).
- Secondary storage: metrics are empty files whose modification time is the value plus 1,000,000,000 (`<data dir>/metrics/render_count.stamp`, `last_render_ms.stamp`). `increment` stats, writes, then stats again to read back what it just wrote (`telemetry.py`).
- The asset index is the same trick: `<data dir>/index/<cow>.stamp` with the line count in the mtime. Nothing ever reads it except `verify` (`index.py`).

## Patterns
- `CowAssetPlugin` ABC with one implementation, `LineDirectoryPlugin`.
- `BorderStrategy` ABC with one strategy, `SpeechBorderStrategy`.
- `ServiceContainer` (DI) that builds one pipeline per process; `settings` is resolved once and thrown away.
- `RenderSettings`: 20 validated fields, read by nothing.
- `FeatureFlags`: 7 flags, all on, never evaluated (the pipeline holds them and never calls `enabled`).
- `RenderEventBus` publishes `frame.composited` to zero subscribers, 3 times per call.
- `OutputCircuitBreaker` around the one stdout write; it never counts a failure, so it can never open.
- Each of the 4 stages is an `async def` that blocks in `time.sleep`, run with its own `asyncio.run` (12 event loops per call).

## Resilience theatre
- `RetryPolicy` with exponential backoff (60 ms, 120 ms, ...) wraps every stage, all of them pure.
- `FaultInjector` fails the first attempt of a stage with probability 0.35 (seeded by `SLOP_SEED`), so the retry path runs about 4 times per call. Only first attempts fail, so every call succeeds.
- Consistency theatre: every frame is rendered 3 times in full (assets re-read each time) and compared (`RenderPipeline.render`).

## Noise on stderr (none of it matters)
- `TerminalCapabilityWarning` about the terminal width; the detected width is then ignored, and an ERROR line says so.
- `asset index corruption detected ... rebuilding` on every start: `verify` compares a CRC32 of the cow name with a stamp that holds the line count, so it never matches.
- A full `KeyError: 'ruminant-mono'` traceback for a "font cache miss" (the font table dict is always empty), then `recovered: glyph metrics regenerated`.
- `DeprecationWarning` for `legacy_wrap`, which the pipeline itself calls, 3 times per call (without `-n`).
- Retry WARNINGs for the injected faults.
- ERROR level for normal events: discovery done, index rebuilt, event delivered to 0 subscribers, consistency verified, circuit closed, metrics committed.

## Docs that lie
- `GlyphMetricsCache.width`: "O(1)" and "East Asian Width table"; it loops over every character and every glyph is 1 wide. Its cache stores every miss and is never warmed.
- `wrap_paragraph`: "Knuth-Plass total-fit algorithm"; it is greedy first-fit (as Text::Wrap is), scanning back from the limit for each line.
- `MessageLexer`: "grapheme clusters for the total-fit line breaker"; it splits on whitespace with a regex.
- `RenderPipeline.render -> bytes` returns `str`; the class docstring says "concurrent", the stages run one after another.
- `RuntimeEnvironment.rng`: "cryptographically secure"; it is `random.Random`.
- `RetryPolicy`: "with full jitter"; there is no jitter.
- `RenderSettings`: "consumed by every pipeline stage"; consumed by none. `FeatureFlags`: "evaluated per request"; never.
- `AssetIndex`: "so lookups stay O(1)"; no lookup uses it.
- `probe_terminal_width`: "terminfo capability database"; it is `os.get_terminal_size`.
- `LineDirectoryPlugin`: says the OS page cache deduplicates identical rows. It does not.

## Delays (at `SLOP_SLEEP_SCALE=1`, default cow)
- 0.04 s per cow per discovery; discovery runs 8 times per call (bootstrap, verify, rebuild, one per rebuilt cow, one per render): about 0.64 s.
- Index rebuild: 0.12 s per cow, about 0.24 s.
- 0.1 s after the terminal probe, 0.15 s after the glyph warm-up, 0.1 s before the metrics write.
- 0.03 s per stage, 12 stages: 0.36 s.
- Retry backoff: 0.06 s per injected fault, about 0.25 s on average.
- Measured total: about 2.0 s p50 per call (see README).

## Bounds
- Message up to 4,096 characters, wrap column 2 to 1,024, 256 cows, 512 lines per cow, 4,096 bytes per line file.
- `SLOP_SLEEP_SCALE` clamped to 0..10, one pause at most 2 s, 4 attempts per retry.
- Writes only under the data dir: 2 metric stamps and one index stamp per cow.
