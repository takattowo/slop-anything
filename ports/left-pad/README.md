# Leftpad Layout Engine

![build](https://img.shields.io/badge/build-passing-brightgreen) ![tests](https://img.shields.io/badge/tests-44%20passed-brightgreen) ![parity](https://img.shields.io/badge/npm%20left--pad-1.3.0%20parity-blue) ![python](https://img.shields.io/badge/python-3.13-blue) ![latency](https://img.shields.io/badge/p50-0.82%20s-orange)

**Enterprise-grade left padding.** Leftpad is a staged text-layout engine that reproduces npm `left-pad` 1.3.0 byte for byte, with a pluggable strategy registry, a durable memo store, glyph-paced rendering and built-in telemetry.

## Features

- **Exact npm parity.** Same doubling algorithm as `left-pad@1.3.0`, including multi-character fills that overshoot the target, `0` as a fill, JavaScript `String()` conversion of `null`/`true`/`false`, and UTF-16 length measurement (an emoji counts as 2, as in JavaScript).
- **Pluggable padding strategies.** A strategy registry with plugin discovery, plus a vendored reference implementation that takes over automatically when discovery fails.
- **Layout pipeline.** Measure, resolve strategy, compose, render: four isolated stages with lifecycle events.
- **Triple-verified output.** Every result is computed three times and cross-checked before it leaves the engine.
- **Durable layout registry.** Results are persisted as native Python and re-imported on every request, so the registry is always exactly what is on disk.
- **Glyph-stream renderer.** Output is streamed glyph by glyph with frame pacing, on its own event loop.
- **Observability built in.** Counters, shard routing and per-request timings are archived to a compressed telemetry bundle.
- **Hard limits.** Target length up to 10,000, values up to 100,000 characters, padding up to 100,000 characters. Anything larger is rejected with `ValueError`.

## Quick start

No install step. Standard library only (`pytest` for the tests). Tested on Python 3.13.

PowerShell:

```powershell
python ports/left-pad abc 5        # "  abc"
python ports/left-pad 5 3 0        # "005"
python ports/left-pad x 4 ab       # "abababx"  (npm overshoot, faithfully reproduced)
```

POSIX shell:

```sh
python3 ports/left-pad abc 5
python3 ports/left-pad 5 3 0
```

Run from the repository root (or pass the full path to `ports/left-pad` from anywhere). stdout carries only the padded string and a newline; diagnostics go to stderr, so `2>$null` (PowerShell) or `2>/dev/null` (POSIX) gives clean output. Missing arguments print usage on stderr and exit with code 2, as does a length over 10,000.

### Library

```python
import sys
sys.path.insert(0, "ports/left-pad/src")

from leftpad import left_pad

left_pad("foo", 5)       # '  foo'
left_pad(1, 2, 0)        # '01'
left_pad(None, 6)        # '  null'
left_pad("a", 4, "xy")   # 'xyxyxya'
left_pad("foo", "abc")   # 'foo'  (a non-numeric length behaves like NaN)
```

`left_pad` emits a `DeprecationWarning` pointing to `LayoutEngine.layout()`, which takes the same arguments.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `SLOP_SLEEP_SCALE` | `1` | Multiplies all frame pacing. `0` disables it. Clamped to 0..10. |
| `SLOP_SEED` | unset | Seeds shard routing and pacing jitter. |
| `SLOP_DATA_DIR` | `./.slop-data/left-pad` | Where the layout registry and telemetry live. Nothing is written anywhere else. |

## Architecture

```
CLI / left_pad()
   -> LayoutEngine            (settings, request normalisation, limits)
      -> LayoutRegistryStore  (_layout_registry.py, imported with importlib)
      -> LayoutPipeline
           MeasureStage -> ResolveStrategyStage -> ComposeStage -> RenderStage
                              |                       |
                     StrategyRegistry          3x consistency check
                     + vendored 1.3.0          + registry memo check
      -> TelemetryArchive     (layout_telemetry.zip)
```

The registry keeps at most 128 entries (oldest evicted first) and does not memoise results longer than 2,048 characters, so `_layout_registry.py` stays small.

## Why

Padding is on the critical path of every log line, invoice and terminal table. It deserves the same rigour as the rest of the stack: verification, durability, observability and graceful degradation.

## Performance

Deterministic, paced latency. Measured on the maintainer's Windows workstation, Python 3.13, `SLOP_SLEEP_SCALE=1`, fresh data directory, wall clock per CLI process with PowerShell `Measure-Command` (stderr discarded):

| Workload | Runs | p50 | max |
|---|---|---|---|
| `abc 5` | 11 | 0.815 s | 1.096 s (the 11th request, vendored fallback) |
| `x 10000` | 5 | 1.779 s | 1.823 s |
| `python -c pass` (baseline) | 1 | 0.232 s | |

Pacing is bounded: at most about 1.73 s of budgeted delay per request at scale 1 (0.25 s ±10% registry rebuild, 0.15 s verification, up to 1.0 s glyph streaming, 0.3 s on fallback requests), plus up to 0.75 s of write backoff when another process holds the layout registry. All of it scales with `SLOP_SLEEP_SCALE`.

## Tests

PowerShell:

```powershell
cd ports/left-pad
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m pytest -q -p no:cacheprovider
```

POSIX shell:

```sh
cd ports/left-pad
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
```

The suite runs with pacing off, a fixed seed and a temporary data directory.

## Engineering ledger

Design trade-offs are tracked in [SLOP.md](SLOP.md).
