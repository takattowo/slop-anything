# Ruminant

![build](https://img.shields.io/badge/build-passing-brightgreen) ![tests](https://img.shields.io/badge/tests-33%20passed-brightgreen) ![parity](https://img.shields.io/badge/cowsay-3.03%20parity-blue) ![python](https://img.shields.io/badge/python-3.13-blue) ![latency](https://img.shields.io/badge/p50-2.0%20s-orange)

**The terminal rendering platform for bovine speech.** Ruminant is a staged, plugin-driven renderer that reproduces classic cowsay 3.03 output byte for byte, with a self-healing asset index, a resilient layout engine, triple-verified frames and durable telemetry.

## Features

- **Byte-exact cowsay 3.03 output.** Same balloon geometry, same Text::Wrap line breaking (lines up to `width - 1` columns, collapsed whitespace, hard splits for long words, paragraph breaks on a newline followed by whitespace), LF line endings on every platform.
- **Scanline asset storage.** Every cow is a folder of numbered line files (`cows/default/0001.line` ...). Each scanline is independently versioned and assembled fresh on every request, so a change on disk is live on the next call.
- **Plugin registry with live discovery.** Asset formats are plugins; cows are discovered by scanning the asset tree, never from a stale list.
- **Self-healing asset index.** A CRC32 index is verified at startup and rebuilt automatically whenever corruption is detected.
- **Four-stage render pipeline.** Asset, layout, bubble and composite stages, each on its own event loop, with lifecycle events.
- **Triple-verified frames.** Every frame is rendered three times and compared before it reaches your terminal.
- **Resilient layout.** Exponential backoff retries on every stage, plus a circuit breaker on stdout.
- **Durable telemetry.** Render counts and timings are persisted with zero serialization overhead, in filesystem timestamps.
- **Hard limits.** Messages up to 4,096 characters and wrap columns 2 to 1,024; anything outside is rejected with a usage error (exit 2). The asset tree is scanned up to 256 entries, and anything past that is skipped with a warning. A cow with more than 512 lines, a line file over 4,096 bytes or a line file that is not UTF-8 is rejected as a malformed asset (exit 1 when you ask for it; other cows keep working).

## Quick start

No install step. Standard library only (`pytest` for the tests). Tested on Python 3.13. Run from the repository root, or pass the full path to `ports/cowsay` from anywhere.

PowerShell:

```powershell
python ports/cowsay "Hello, world"
python ports/cowsay -f tux "Penguins welcome"
python ports/cowsay -W 20 -e ^^ -T "U " Ruminant renders every frame three times
python ports/cowsay -n "first line`n  second line"
python ports/cowsay -l
python ports/cowsay "Hello, world" 2>$null          # result only
```

POSIX shell:

```sh
python3 ports/cowsay "Hello, world"
python3 ports/cowsay -f tux "Penguins welcome"
python3 ports/cowsay -W 20 -e '^^' -T 'U ' Ruminant renders every frame three times
python3 ports/cowsay -n "$(printf 'first line\n  second line')"
python3 ports/cowsay -l
python3 ports/cowsay "Hello, world" 2>/dev/null     # result only
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

## Usage

```
cowsay [-f cowfile] [-W wrapcolumn] [-e eye_string] [-T tongue_string] [-n] [-l] message ...
```

| Option | Meaning | Default |
|---|---|---|
| `-f NAME` | Cow to render (`default`, `tux`, or any folder you add under `src/ruminant/cows/`) | `default` |
| `-W N` | Wrap column; lines are at most `N - 1` characters, as in cowsay | `40` |
| `-e EYES` | Eyes; the first two characters are used | `oo` |
| `-T TONGUE` | Tongue; the first two characters are used | two spaces |
| `-n` | No wrapping: message lines are kept as given, tabs expanded to 8 | off |
| `-l` | List available cows | |
| `-h` | Usage on stdout, exit 0 | |

Message words are joined with single spaces. stdout carries only the frame. All diagnostics go to stderr. Exit codes: `0` success, `1` unknown or malformed cow, `2` bad usage (no message, bad option, width or length out of range). Ruminant never reads stdin.

### Environment

| Variable | Effect | Default |
|---|---|---|
| `SLOP_SLEEP_SCALE` | Multiplies every pacing interval (clamped to 0..10) | `1` |
| `SLOP_SEED` | Seeds the fault injector | unseeded |
| `SLOP_DATA_DIR` | Where the index and telemetry live | `<cwd>/.slop-data/cowsay/` |

### Adding a cow

Create `src/ruminant/cows/<name>/` and put one file per scanline in it: `0001.line`, `0002.line`, ... (lexical order, no trailing newline needed). `$thoughts`, `$eyes` and `$tongue` are substituted at render time. An empty file is an empty line. The registry discovers the folder on the next call; `-l` lists it.

## Architecture

```
cli ──> ServiceContainer ──> RenderPipeline
                               ├─ asset      CowRegistry ─> LineDirectoryPlugin ─> cows/<name>/*.line
                               ├─ layout     MessageLexer ─> fill / wrap_paragraph
                               ├─ bubble     BubbleComposer ─> SpeechBorderStrategy, GlyphMetricsCache
                               └─ composite  FrameCompositor (placeholder resolution)
               bootstrap: terminal probe, discovery, AssetIndex verify/rebuild, glyph cache warm-up
               every stage: RetryPolicy (exponential backoff) ; output: OutputCircuitBreaker
               telemetry: MetricsStore (<data dir>/metrics/*.stamp)
```

## Why

A cow is a production asset. It deserves versioning at scanline granularity, an index that heals itself, a renderer that checks its own work three times, and telemetry that survives a crash. Ruminant treats every `moo` like a deploy.

## Performance

Ruminant paces itself so the terminal driver is never overwhelmed. Measured on the development PC (Windows, Python 3.13, `SLOP_SLEEP_SCALE=1`, unseeded): wall-clock time of a full `python ports/cowsay ...` subprocess, timed with `time.perf_counter`, 10 runs each:

| Command | min | p50 | max |
|---|---|---|---|
| `Hello, world` | 1.88 s | 1.99 s | 2.12 s |
| 3-line wrapped message | 1.93 s | 2.00 s | 2.06 s |
| `-f tux hi` | 1.82 s | 1.97 s | 2.24 s |

With `SLOP_SLEEP_SCALE=0` the same `Hello, world` call takes 0.15 s p50. Consistent, predictable, two-second latency, every time.

## Compatibility notes

- Bubble and wrapping were checked against Perl's Text::Wrap 2024.001 running cowsay 3.03's balloon code on 703 generated messages and widths 2 to 80: all identical.
- `-n` works on the message arguments (cowsay 3.03 uses `-n` with stdin; Ruminant never reads stdin).
- Lengths are counted in characters; cowsay 3.03 under Perl counts UTF-8 bytes, so non-ASCII messages pad differently there.
- Not implemented: `cowthink`, the `-b -d -g -p -s -t -w -y` face presets, `-f` with a file path, `COWPATH`.

## Tests

```powershell
cd ports/cowsay
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -p no:cacheprovider
```

```sh
cd ports/cowsay && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
```
