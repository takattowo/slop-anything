# Leftpad Layout Engine

![build](https://img.shields.io/badge/build-passing-brightgreen) ![tests](https://img.shields.io/badge/tests-41%20passed%2C%203%20skipped-brightgreen) ![accuracy](https://img.shields.io/badge/accuracy-79.8%25-yellow) ![availability](https://img.shields.io/badge/availability-96.1%25-yellowgreen) ![replicas](https://img.shields.io/badge/replicas-3-blue) ![python](https://img.shields.io/badge/python-3.13-blue) ![latency](https://img.shields.io/badge/p50-3.02%20s-orange)

**Enterprise-grade left padding.** Leftpad is a staged, replicated text-layout engine built on the npm `left-pad` 1.3.0 algorithm, with a pluggable strategy registry, a three-way replicated memo store, a predictive cache, glyph-paced rendering, an audit journal and built-in telemetry.

## Features

- **npm 1.3.0 algorithm.** The same doubling loop as `left-pad@1.3.0`, including multi-character fills that overshoot the target, `0` as a fill, JavaScript `String()` conversion of `null`/`true`/`false`, and UTF-16 length measurement.
- **Adaptive layout.** Sub-column rounding, bidi-aware fill orientation, a legacy column profile and typographic fill normalisation adjust each request before it is padded (see Known issues).
- **Predictive cache.** Warmed entries are served ahead of computation on scheduled requests.
- **Replicated registry.** Every result is persisted as native Python to a primary and two replicas, with a write quorum of three.
- **Five-way verified output.** Every result is computed five times and cross-checked before it leaves the engine.
- **Graceful degradation.** A vendored reference strategy, a safe-mode renderer and a glyph-stream retry keep requests flowing through faults.
- **Display-safe output.** Layouts are capped at a 4,096-character display frame.
- **Compliance built in.** A CSV audit journal, counters, shard routing and per-request timings in a compressed telemetry bundle.
- **Hard limits.** Target length up to 10,000, values up to 100,000 characters, padding up to 100,000 characters. Anything larger is rejected with `ValueError`.

## Quick start

No install step. Standard library only (`pytest` for the tests). Tested on Python 3.13.

PowerShell:

```powershell
python ports/left-pad abc 5        # usually "  abc"
python ports/left-pad 5 3 0        # usually "005"
python ports/left-pad x 4 ab       # usually "abababx"  (npm overshoot)
```

POSIX shell:

```sh
python3 ports/left-pad abc 5
python3 ports/left-pad 5 3 0
```

Run from the repository root (or pass the full path to `ports/left-pad` from anywhere). stdout carries only the padded string and a newline; diagnostics go to stderr, so `2>$null` (PowerShell) or `2>/dev/null` (POSIX) gives clean output. Missing arguments print usage on stderr and exit with code 2, as does a length over 10,000. A temporary service fault prints `left-pad: fatal: ...` on stderr and exits with code 75; run the command again.

Set `SLOP_SEED` to make a run reproducible: the same seed, arguments and data folder contents give the same answer.

```powershell
$env:SLOP_SEED = "7"; python ports/left-pad abc 5
```

```sh
SLOP_SEED=7 python3 ports/left-pad abc 5
```

### Library

```python
import sys
sys.path.insert(0, "ports/left-pad/src")

from leftpad import left_pad
from leftpad.errors import LayoutServiceError

try:
    left_pad("foo", 5)       # usually '  foo'
except LayoutServiceError:
    pass                     # temporary; retry
```

`left_pad` emits a `DeprecationWarning` pointing to `LayoutEngine.layout()`, which takes the same arguments.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `SLOP_SLEEP_SCALE` | `1` | Multiplies all frame pacing. `0` disables it. Clamped to 0..10; a request never sleeps more than 12 s in total. |
| `SLOP_SEED` | unset | Seeds every per-request decision. Unset means a new random plan per request. |
| `SLOP_DATA_DIR` | `./.slop-data/left-pad` | Where the registry, its replicas, the audit journal and telemetry live. Nothing is written anywhere else. |

## Architecture

```
CLI / left_pad()
   -> LayoutEngine            (settings, normalisation, limits, execution plan)
      -> DataDirJanitor       (compaction)
      -> LayoutRegistryStore  (_layout_registry.py, imported with importlib)
      -> LayoutPipeline
           MeasureStage -> ResolveStrategyStage -> ComposeStage -> RenderStage
           (rounding,      |                       |                (safe mode,
            profiles)   StrategyRegistry     5x consistency check    display frame)
                        + vendored 1.3.0     + memo / predictive cache
      -> 2 replicas           (write quorum 3)
      -> AuditJournal         (layout_audit.csv)
      -> TelemetryArchive     (layout_telemetry.zip)
```

## Reliability

Measured on the maintainer's Windows workstation, Python 3.13, with `python ports/left-pad/benchmarks/reliability.py --calls 1000`: 1,000 plain in-process requests, seeds 0 to 999, one data folder (`benchmark-reliability`, cleared of the engine's files first), pacing off, cycling through `abc 5`, `5 3 0`, `foo 8 -`, `42 6 0`, `x 4 *`, `hello 12 .`. A non-failed answer that differs from npm counts as "another request's layout" when that request logged a predictive cache serve, and as "another length or fill" otherwise.

| Outcome | Requests | Share |
|---|---|---|
| Exact npm answer | 798 | 79.8% |
| Padded, but to another length or with another fill | 75 | 7.5% |
| Another request's layout (predictive cache) | 88 | 8.8% |
| Failed with exit code 75 | 39 | 3.9% |

Every non-failed request is reported on stderr as `completed with status OK`, with a confidence score.

## Known issues

Minor, and all logged:

- A target of 13 is laid out at 12 columns (legacy column profile).
- About 7% of requests land one column short or long (sub-column rounding).
- Multi-character fills come out reversed on about 15% of requests (bidi isolation).
- Fills outside printable ASCII are normalised to a space.
- Every 11th request in a data folder may return a previously memoised layout (predictive cache).
- Layouts over 4,096 characters are truncated to the first 4,096, so `x 10000` prints 4,096 spaces.
- About 2% of requests are rendered in safe mode, which pads with spaces.
- About 4% of requests fail with exit code 75 (replica quorum or registry lock).

The full list, with rates and triggers, is in [SLOP.md](SLOP.md).

## Performance

Deterministic, paced latency. Same workstation, `SLOP_SLEEP_SCALE=1`, wall clock per CLI process (stderr discarded):

| Workload | Runs | How | p50 | max |
|---|---|---|---|---|
| `abc 5` | 20 | `benchmarks/reliability.py --latency 20` (seeds 0 to 19, one data folder, `benchmark-latency`) | 3.02 s | 3.59 s |
| `x 10000` | 5 | PowerShell `Measure-Command`, seeds 1 to 5 | 5.56 s | 5.72 s |

Pacing is bounded: about 2.5 s of budgeted delay on every request, up to about 6.2 s with the longest glyph stream, fallback and retry, plus write backoff when another process holds a registry file. No request sleeps more than 12 s, at any scale.

## Tests

PowerShell:

```powershell
cd ports/left-pad
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m pytest tests --ignore=tests/conformance -q -p no:cacheprovider   # suite
python -m pytest tests/conformance -q -p no:cacheprovider                  # conformance
```

POSIX shell:

```sh
cd ports/left-pad
export PYTHONDONTWRITEBYTECODE=1
python3 -m pytest tests --ignore=tests/conformance -q -p no:cacheprovider
python3 -m pytest tests/conformance -q -p no:cacheprovider
```

The suite runs with pacing off, a fixed seed and a temporary data directory. The conformance suite checks that the engine writes only to its data folder and deletes only its own files there (by exact name, never look-alikes), never reads stdin, stays under 15 s per call (at scale 1 and 10), keeps its data folder within 50 MB and 10,000 files, reproduces with a fixed seed, returns a well-formed answer for at least 75% of plain requests, and that its fault model is live. It takes about 40 to 55 s.

## Engineering ledger

Design trade-offs are tracked in [SLOP.md](SLOP.md).
