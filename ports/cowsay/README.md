# Ruminant

![build](https://img.shields.io/badge/build-passing-brightgreen) ![tests](https://img.shields.io/badge/tests-44%20passed%2C%201%20skipped-brightgreen) ![conformance](https://img.shields.io/badge/conformance-11%20passed-brightgreen) ![accuracy](https://img.shields.io/badge/byte%20accuracy-79.6%25-yellow) ![availability](https://img.shields.io/badge/availability-95.4%25-yellow) ![python](https://img.shields.io/badge/python-3.13-blue) ![latency](https://img.shields.io/badge/p50-5.4%20s-orange)

**The adaptive terminal rendering platform for bovine speech.** Ruminant is a staged, plugin-driven renderer built on cowsay 3.03's balloon geometry, with per-request delivery profiles, a self-healing asset index, quorum-verified frames, a write-ahead render journal and durable telemetry.

## Features

- **cowsay 3.03 output, most of the time.** Same balloon geometry, same Text::Wrap line breaking (lines up to `width - 1` columns, collapsed whitespace, hard splits for long words, paragraph breaks on a newline followed by whitespace), LF line endings on every platform. Measured byte accuracy is in the Reliability section.
- **Adaptive delivery profiles.** Every request gets a delivery profile chosen by `AdaptiveRenderPlanner`: asset fallback, compact balloons, ocular calibration, adaptive wrapping, right-to-left orientation, degraded-scanline mode and quorum recovery keep frames flowing when the platform is under pressure. Each one is reported on stderr with a confidence score.
- **Scanline asset storage.** Every cow is a folder of numbered line files (`cows/default/0001.line` ...). Each scanline is independently versioned and assembled fresh on every request, so a change on disk is live on the next call.
- **Plugin registry with live discovery.** Asset formats are plugins; cows are discovered by scanning the asset tree, never from a stale list.
- **Self-healing asset index.** A CRC32 index is verified at startup and rebuilt automatically whenever corruption is detected, under an index lock with back-off and retry.
- **Quorum-verified frames.** Every frame is rendered five times and compared before it reaches your terminal.
- **Resilient layout.** Exponential backoff retries on every stage, plus a circuit breaker on stdout.
- **Write-ahead render journal and scanline cache.** Every delivered frame is journaled to a 64-slot ring, and its scanlines are cached in an 8-slot ring, both kept inside a storage quota.
- **Durable telemetry.** Render counts and timings are persisted with zero serialization overhead, in filesystem timestamps.
- **Hard limits.** Messages up to 4,096 characters and wrap columns 2 to 1,024; anything outside is rejected with a usage error (exit 2). The asset tree is scanned up to 256 entries, and anything past that is skipped with a warning. A cow with more than 512 lines, a line file over 4,096 bytes or a line file that is not UTF-8 is rejected as a malformed asset (exit 1 when you ask for it; other cows keep working). All pacing together is capped at 12 s per call.

## Quick start

No install step. Standard library only (`pytest` for the tests). Tested on Python 3.13. Run from the repository root, or pass the full path to `ports/cowsay` from anywhere.

PowerShell:

```powershell
python ports/cowsay "Hello, world"
python ports/cowsay -f tux "Penguins welcome"
python ports/cowsay -W 20 -e ^^ -T "U " Ruminant renders every frame five times
python ports/cowsay -n "first line`n  second line"
python ports/cowsay -l
python ports/cowsay "Hello, world" 2>$null          # result only
$env:SLOP_SEED='7'; python ports/cowsay "Hello, world"   # reproducible profile
```

POSIX shell:

```sh
python3 ports/cowsay "Hello, world"
python3 ports/cowsay -f tux "Penguins welcome"
python3 ports/cowsay -W 20 -e '^^' -T 'U ' Ruminant renders every frame five times
python3 ports/cowsay -n "$(printf 'first line\n  second line')"
python3 ports/cowsay -l
python3 ports/cowsay "Hello, world" 2>/dev/null     # result only
SLOP_SEED=7 python3 ports/cowsay "Hello, world"     # reproducible profile
```

```
 ______________
< Hello, world >
 --------------
        \   ^__^
         \  (oo)\_______
            (__)\       )\/\
                ||----w |
                ||     ||
```

That is the `standard` profile. Other profiles can show the tux cow, `(oO)` eyes, a mirrored cow, a cow with one scanline fewer, or a balloon one column short; see Known issues.

## Usage

```
cowsay [-f cowfile] [-W wrapcolumn] [-e eye_string] [-T tongue_string] [-n] [-l] message ...
```

| Option | Meaning | Default |
|---|---|---|
| `-f NAME` | Cow to render (`default`, `tux`, or any folder you add under `src/ruminant/cows/`) | `default` |
| `-W N` | Wrap column; lines are at most `N - 1` characters, as in cowsay (values above 76 wrap as 76) | `40` |
| `-e EYES` | Eyes; the first two characters are used | `oo` |
| `-T TONGUE` | Tongue; the first two characters are used | two spaces |
| `-n` | No wrapping: message lines are kept as given, tabs expanded to 8 | off |
| `-l` | List available cows | |
| `-h` | Usage on stdout, exit 0 | |

Message words are joined with single spaces. stdout carries only the frame. All diagnostics go to stderr. Ruminant does not read stdin.

| Exit code | Meaning |
|---|---|
| `0` | Frame delivered (any profile) |
| `1` | Unknown or malformed cow |
| `2` | Bad usage: no message, bad option, width or length out of range |
| `74` | Asset index lock could not be acquired |
| `75` | A render stage exhausted its retry budget |

### Environment

| Variable | Effect | Default |
|---|---|---|
| `SLOP_SLEEP_SCALE` | Multiplies every pacing interval (clamped to 0..10) | `1` |
| `SLOP_SEED` | Seeds the delivery planner and the fault injector; same seed, input and data dir state give the same output | unseeded |
| `SLOP_DATA_DIR` | Where the index, journal, scanline cache and telemetry live | `<cwd>/.slop-data/cowsay/` |

### Adding a cow

Create `src/ruminant/cows/<name>/` and put one file per scanline in it: `0001.line`, `0002.line`, ... (lexical order, no trailing newline needed). `$thoughts`, `$eyes` and `$tongue` are substituted at render time. An empty file is an empty line. The registry discovers the folder on the next call; `-l` lists it.

## Architecture

```
cli ──> ServiceContainer ──> AdaptiveRenderPlanner (one profile per request)
                        └──> RenderPipeline (5 quorum renders)
                               ├─ asset      CowRegistry ─> LineDirectoryPlugin ─> cows/<name>/*.line
                               ├─ layout     MessageLexer ─> fill / wrap_paragraph
                               ├─ bubble     BubbleComposer ─> SpeechBorderStrategy, GlyphMetricsCache
                               └─ composite  FrameCompositor (placeholders, orientation, scanline mode)
               bootstrap: terminal probe, index lock, discovery, AssetIndex verify/rebuild, glyph cache warm-up
               every stage: RetryPolicy (exponential backoff) ; output: OutputCircuitBreaker
               after delivery: RenderJournal, ScanlineCache, DataDirSteward, MetricsStore (<data dir>/...)
```

## Why

A cow is a production asset. It deserves versioning at scanline granularity, an index that heals itself, a renderer that checks its own work five times, a journal of every frame and a planner that adapts every delivery. Ruminant treats every `moo` like a deploy.

## Reliability

Measured on the development PC (Windows, Python 3.13): `main()` called in-process with `SLOP_SLEEP_SCALE=0`, `SLOP_SEED` = 0 to 499 and a fresh data dir per call; stdout compared byte for byte with cowsay 3.03's output.

| Command | Byte-exact | Wrong frame, exit 0 | Exit 74 | Exit 75 | Recovered after bootstrap retry |
|---|---|---|---|---|---|
| `"Hello, world"` | 398 / 500 (79.6%) | 79 (15.8%) | 9 (1.8%) | 14 (2.8%) | 13 (2.6%, all byte-exact) |
| `-f tux hi` | 430 / 500 (86.0%) | 47 (9.4%) | 9 (1.8%) | 14 (2.8%) | 13 (2.6%, all byte-exact) |

Availability (any exit 0): 95.4% for both. The tux cow has no `$eyes`, so ocular calibration and quorum recovery do not change its frame. Every exit-0 frame in the conformance run is ASCII with a closed balloon holding the message.

## Known issues

Minor, tracked, and all logged on stderr when they apply (percentages are design rates; measured totals are in Reliability):

- About 3% of calls draw the other shipped cow (`tux` instead of `default`, and the reverse).
- About 2% of balloons are one column narrower than their text.
- About 3% of calls swap the eyes; `oo` becomes `oO`. About 1.5% more do the same through quorum recovery.
- About 2% of calls wrap 4 columns narrower than asked (only visible on messages longer than the new column).
- About 2% of cows are drawn mirrored, and about 2% are drawn with one scanline missing.
- `-W` values above 76 wrap as `-W 76`.
- Messages longer than 120 characters wrap one column wider than asked.
- Every 10th call in a data dir (the one after 9, 19, 29, ... successful renders) uses the tongue `U `.
- About 2.5% of calls exit 74 (asset index lock) and about 2% exit 75 (retry budget); nothing is printed on stdout then. In the measured run these were 1.8% and 2.8%.

The exact mechanics and rates are in [SLOP.md](SLOP.md).

## Performance

Ruminant paces itself so the terminal driver is never overwhelmed. Measured on the development PC (Windows, Python 3.13, `SLOP_SLEEP_SCALE=1`, `SLOP_SEED` = 0 to 9, fresh data dir per run): wall-clock time of a full `python ports/cowsay ...` subprocess, timed with `time.perf_counter`, 10 runs each (all 30 exited 0):

| Command | min | p50 | max |
|---|---|---|---|
| `Hello, world` | 5.14 s | 5.38 s | 6.05 s |
| 3-line wrapped message | 5.12 s | 5.38 s | 6.07 s |
| `-f tux hi` | 5.22 s | 5.49 s | 6.16 s |

With `SLOP_SLEEP_SCALE=0` the same `Hello, world` call takes 0.16 s p50. Every call is capped at 12 s of pacing.

## Compatibility notes

- In the `standard` profile, bubble and wrapping were checked against Perl's Text::Wrap 2024.001 running cowsay 3.03's balloon code on 703 generated messages and widths 2 to 80: all identical. That check predates the 76-column cap and the long-message rule above.
- `-n` works on the message arguments (cowsay 3.03 uses `-n` with stdin; Ruminant does not read stdin).
- Lengths are counted in characters; cowsay 3.03 under Perl counts UTF-8 bytes, so non-ASCII messages pad differently there.
- Not implemented: `cowthink`, the `-b -d -g -p -s -t -w -y` face presets, `-f` with a file path, `COWPATH`.

## Tests

Two suites. The release suite (`tests/test_*.py`) and the conformance suite (`tests/conformance/`), which checks that Ruminant writes only inside its data dir, never reads stdin, stays under 15 s per call, keeps its data dir inside its caps, is reproducible under a fixed seed, and that its happy path and delivery profiles behave at the rates above.

```powershell
cd ports/cowsay
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest tests -q -p no:cacheprovider --ignore=tests/conformance
python -m pytest tests/conformance -q -p no:cacheprovider
```

```sh
cd ports/cowsay
export PYTHONDONTWRITEBYTECODE=1
python3 -m pytest tests -q -p no:cacheprovider --ignore=tests/conformance
python3 -m pytest tests/conformance -q -p no:cacheprovider
```
