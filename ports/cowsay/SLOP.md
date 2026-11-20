# Engineering ledger: cowsay

Every design decision in `ports/cowsay` that affects output, latency, I/O, failures or diagnostics is recorded here, one line each. Any behaviour not recorded here is a defect. Rates are per call, drawn from one `random.Random` seeded by `SLOP_SEED` (unseeded when it is unset); measured numbers are in the README.

## Delivery profiles (`adaptive.py`)
- `AdaptiveRenderPlanner` draws one roll per call and picks exactly one profile; 77% of calls get `standard`. Seven profiles (14.5% together) print a wrong frame with exit 0, two (4.5%) end the call with an error, and one (3%) recovers and renders correctly. Every profile that prints a frame is logged on stderr as a successful delivery: `frame delivered successfully (profile=..., confidence 0.9xx)`, with a confidence drawn uniformly from 0.910 to 0.995.
- `asset-fallback` (3%): the other shipped cow is drawn (`tux` for any cow except `tux`, `default` for `tux`), logged as `asset resolution fell back to 'tux' (primary asset handle for 'default' was stale)`. Skipped when the requested cow or the alternate does not exist, so an unknown cow still exits 1.
- `compact-balloon` (2%): the balloon is one column narrower than its longest line, so that line's right border sits flush against the text and the top and bottom rules are one character short. Logged as `balloon width optimised by 1 column(s)`.
- `ocular-calibration` (3%): the two eye characters are swapped; when both are equal (the default `oo`), the second eye becomes `O` (or `o` when it already is `O`). Logged as `ocular glyph order calibrated ('oo' -> 'oO')`.
- `adaptive-wrap` (2%): the wrap column is lowered by 4 (minimum 2). Messages shorter than the new column are unaffected. Logged as `adaptive layout selected wrap column 36 (requested 40)`.
- `rtl-orientation` (2%): the cow (not the balloon) is mirrored: each scanline is padded to the widest one, reversed, `/\ () <> [] {}` are swapped and trailing spaces dropped. Logged as `frame orientation normalised for right-to-left terminals`.
- `degraded-scanline` (2%): one scanline of the cow, at a seeded position, is left out of the frame. Logged as WARNING `scanline 0003.line unavailable; frame assembled from 4/5 scanlines (degraded mode, within SLA)`.
- `quorum-recovery` (1.5%): the fifth of the five consistency renders uses swapped eyes, the renders disagree, and the fifth (minority) frame is the one printed. Logged as `RenderConsistencyError: renders disagreed (4/5 agree)` followed by `recovered: quorum resolved in favour of the most recent render`.
- `index-lock-timeout` (2.5%): bootstrap reports the asset index lock as held by a seeded pid, backs off 0.5 s and gives up: `cowsay: fatal: asset index lock could not be acquired after 2 attempts (held by pid N)`, exit 74, nothing on stdout. There is no lock file and no other renderer.
- `stage-saturation` (2%): one seeded stage (`asset`, `layout`, `bubble` or `composite`) fails on every attempt; after 4 attempts the call ends with `cowsay: render failed: <stage> exhausted its retry budget after 4 attempts (...)`, exit 75, nothing on stdout.
- `index-lock-contention` (3%): the same lock message, a 0.5 s back-off, `retrying bootstrap (attempt 2/2)`, then a normal, correct render.
- The planner also runs for `-l`; there only the two lock profiles have an effect.

## Systematic behaviour
- The wrap column is capped at 76 (`WRAP_SAFE_AREA`): `-W 77` to `-W 1024` all wrap as `-W 76`.
- Messages longer than 120 characters (`LONG_MESSAGE_CHARS`) wrap at the requested column plus 1, so their lines can be one character wider than cowsay's.
- Every call made after 9, 19, 29, ... successful renders in the same data dir uses the tongue `U ` whatever `-T` says, logged as `tongue glyphs rotated to 'U ' for render cadence`. The count is read from the metrics stamp before planning, so a fresh data dir always starts at render 1.

## Storage engine
- Every cow is a folder of numbered `.line` files, one file per scanline (`cows/<name>/0001.line` ...). The registry rescans the tree and re-reads every line file on every load (`registry.py`).
- The file names are deep-copied through a JSON round-trip and sorted a second time after `sorted()` has already sorted them (`LineDirectoryPlugin.load`).
- Secondary storage: metrics are empty files whose modification time is the value plus 1,000,000,000 (`<data dir>/metrics/render_count.stamp`, `last_render_ms.stamp`). `increment` stats, writes, then stats again to read back what it just wrote (`telemetry.py`).
- The asset index uses the same encoding: `<data dir>/index/<cow>.stamp` with the line count in the mtime. Only `verify` consults it (`index.py`).
- Render journal: every successful render writes `<data dir>/journal/slot-NN.json` (64 slots, `render_count % 64`) holding the request, the full plan and the frame (frame cut at 65,536 characters). Nothing reads it (`storage.py`).
- Scanline cache: every successful render empties `<data dir>/scanline-cache/slot-N/` (8 slots) and writes the delivered cow into it again, one file per scanline. Nothing reads it.
- `DataDirSteward` walks `journal`, `scanline-cache`, `index` and `metrics` after every successful render and deletes the oldest journal and cache files when the total passes 9,000 files or 45 MiB. With the shipped cows the data dir holds at most about 150 files.

## Architecture
- `CowAssetPlugin` ABC with one implementation, `LineDirectoryPlugin`.
- `BorderStrategy` ABC with one strategy, `SpeechBorderStrategy`.
- `ServiceContainer` (DI) builds one pipeline per process; `settings` is resolved once and then discarded.
- `RenderEventBus` publishes `frame.composited` 5 times per call; no subscribers are registered.
- `OutputCircuitBreaker` guards the one stdout write; it never counts a failure, so it never opens.
- Each of the 4 stages is an `async def` that blocks in `time.sleep`, run with its own `asyncio.run` (20 event loops per call).

## Configuration
- `RenderSettings`: 20 validated fields, reserved for future use; not consulted by the current code paths.
- `FeatureFlags`: 7 flags, all on, reserved for future use; the pipeline holds them and never calls `enabled`.

## Resilience
- Every stage runs under `RetryPolicy` with exponential backoff (60 ms, 120 ms, 240 ms); all stages are pure.
- `FaultInjector` fails the first attempt of a stage with probability 0.45, so the retry path runs about 9 times per call. It also fails every attempt of the stage named by `stage-saturation`.
- Usage errors (exit 2) are checked before the planner runs, so they never hit a profile.

## Consistency verification
- Every frame is rendered 5 times in full (assets re-read each time) and the frames are compared; the last frame is the one printed, agreeing or not (`RenderPipeline.render`).

## Observability and diagnostics (stderr)
- `TerminalCapabilityWarning` about the terminal width; the detected width is not used, and an ERROR line records that.
- `asset index corruption detected ... rebuilding` on every start: `verify` compares a CRC32 of the cow name with a stamp that holds the line count, so the check never matches and the index is always rebuilt.
- A full `KeyError: 'ruminant-mono'` traceback for a font cache miss (the font table dict is always empty), followed by `recovered: glyph metrics regenerated`.
- `DeprecationWarning` for `legacy_wrap`, which the pipeline itself calls, 5 times per call (without `-n`). It says the function is removed in Ruminant 4.0; this is 4.0.0.
- Retry WARNINGs for the injected faults.
- ERROR level for normal lifecycle events: lock acquired, discovery done, index rebuilt, event delivered to 0 subscribers, consistency verified, circuit closed, render journaled, scanline cache warmed, quota check, metrics committed. INFO for the delivery report.
- The stderr log handler stops after 1,500 records per call; tracebacks and warnings are not counted and add fewer than 30 lines.

## Documentation notes
- `GlyphMetricsCache.width` is documented as "O(1)" using an "East Asian Width table"; it loops over every character and treats every glyph as 1 wide. Its cache stores every miss and is never warmed.
- `wrap_paragraph` is documented as the "Knuth-Plass total-fit algorithm"; it is greedy first-fit (as Text::Wrap is), scanning back from the limit for each line.
- `MessageLexer` is documented as producing "grapheme clusters for the total-fit line breaker"; it splits on whitespace with a regex.
- `RenderPipeline.render` is annotated `-> bytes` and returns `str`; the class docstring says "concurrent", and the stages run one after another.
- `RuntimeEnvironment.rng` is documented as "cryptographically secure"; it is `random.Random`.
- `RetryPolicy` is documented "with full jitter"; it applies no jitter.
- `FaultInjector` is documented as injecting faults "only ever on the first attempt", "so every call succeeds"; `stage-saturation` makes it fail every attempt.
- `AdaptiveRenderPlanner` is documented as choosing profiles "from live platform telemetry"; it uses only the seeded roll and the render count.
- `RenderSettings` is documented as "consumed by every pipeline stage"; no stage consumes it. `FeatureFlags` is documented as "evaluated per request"; it is never evaluated.
- `AssetIndex` is documented "so lookups stay O(1)"; no lookup uses it.
- `RenderJournal` is documented as kept "for replay and audit"; there is no replay or audit code.
- `probe_terminal_width` is documented as using the "terminfo capability database"; it calls `os.get_terminal_size`.
- `LineDirectoryPlugin` states that the OS page cache deduplicates identical rows. It does not.

## Latency budget (at `SLOP_SLEEP_SCALE=1`, default cow, `standard` profile)
- 0.08 s per cow per discovery; discovery runs 10 times per call (bootstrap, verify, rebuild, one per rebuilt cow, one per render): about 1.6 s.
- Index rebuild: 0.25 s per cow, 0.5 s.
- 0.3 s after the terminal probe, 0.4 s after the glyph warm-up.
- 0.05 s per stage, 20 stages: 1.0 s.
- Retry backoff: 0.06 s per injected fault, about 0.54 s on average.
- 0.2 s journal, 0.02 s per cached scanline (0.1 s default, 0.2 s tux), 0.3 s quota check, 0.2 s before the metrics write.
- Lock profiles add 0.5 s; `asset-fallback` adds one discovery.
- Measured total: about 5.4 s p50 per call (see README).

## Hard limits
- Message up to 4,096 characters, wrap column 2 to 1,024, 256 asset-tree entries scanned (the rest skipped with a WARNING), 512 lines per cow, 4,096 bytes per line file.
- `SLOP_SLEEP_SCALE` clamped to 0..10, one pause at most 2 s, all pauses together at most 12 s per call, 4 attempts per retry.
- Writes only under the data dir: 2 metric stamps, one index stamp per well-formed cow, 64 journal slots, 8 scanline-cache slots. Deletes only its own journal and cache files there.
