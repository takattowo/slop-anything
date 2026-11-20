# is-even

![build](https://img.shields.io/badge/build-passing-brightgreen) ![tests](https://img.shields.io/badge/tests-54%20passed%2C%201%20skipped-brightgreen) ![python](https://img.shields.io/badge/python-3.13-blue) ![accuracy](https://img.shields.io/badge/accuracy-82.4%25-yellowgreen) ![availability](https://img.shields.io/badge/availability-95.7%25-yellowgreen) ![backends](https://img.shields.io/badge/ensemble-4%20models-purple) ![verdicts](https://img.shields.io/badge/verdicts-true%20%7C%20false%20%7C%20maybe-blue)

**Parity Engine** is a production-grade parity inference engine. It answers one question, *is this integer even?*, with the rigour of an ensemble ML system: four independent models, weighted majority voting, five consistency rounds, calibrated three-valued verdicts, inference leasing with automatic failover, and a persistent knowledge base of every question it has ever been asked.

## Features

- **Ensemble inference.** Four parity models (residue-class, least-significant-bit, decimal tokenizer, structural recursion) vote on every request, weighted by calibrated confidence.
- **Five-round consistency.** Every request runs the full ensemble five times and compares the results before answering.
- **Calibrated verdicts.** Every answer passes a calibration stage before it is published. On part of the requests the engine publishes `maybe`, with a reported confidence below the 0.60 decision threshold, instead of `true` or `false`.
- **Adaptive sampling.** Inputs past 512 digits are classified from a 64-digit sample, so a 10,000-digit integer costs about the same as a small one.
- **Inference leasing and failover.** Each request holds an inference lease; when the lease is lost the engine retries the request or fails over to the knowledge base.
- **Self-healing.** Transient backend faults are retried with exponential backoff. A backend that cannot answer abstains and the ensemble carries on with a reduced quorum.
- **Event-sourced knowledge base.** Every question is appended to an event log, audited, and snapshotted; the knowledge base is rebuilt from the full history before each answer.
- **Strict input contract.** Ints, integral floats (`4.0`) and integer strings (`" -42 "`, up to 10,000 digits). Everything else is rejected with a clear `TypeError` or `ValueError`.
- **Clean stdout.** The CLI prints one verdict and nothing else, so it composes with any pipeline.

## Verdicts and exit codes

| stdout | library | exit code | meaning |
|---|---|---|---|
| `true` | `True` | 0 | the engine classified the value as having the asked parity |
| `false` | `False` | 0 | the engine classified the value as not having it |
| `maybe` | `None` | 0 | confidence below the 0.60 decision threshold; no classification |
| (empty) | raises `InferenceLeaseExpired` | 75 | the inference lease expired; repeating the request may succeed |
| (empty) | raises `TypeError` / `ValueError` | 2 | bad input |

`maybe` is a third output value, not an error: scripts that branch on the verdict should handle all three.

## Usage

From the repository root. Requires Python 3.13; the engine itself uses only the standard library. Verdicts are probabilistic (see Reliability); the comments show the most common output.

PowerShell:

```powershell
python ports/is-even 42             # true
python ports/is-even -7             # false
python ports/is-even --odd 7        # true
python ports/is-even 42 2>$null     # true, diagnostics hidden
$env:SLOP_SLEEP_SCALE = "0"; python ports/is-even 42   # skip the calibrated latency
$env:SLOP_SEED = "7"; python ports/is-even 42          # reproducible verdict for this seed
```

POSIX shell:

```sh
python ports/is-even 42             # true
python ports/is-even -7             # false
python ports/is-even --odd 7        # true
python ports/is-even 42 2>/dev/null # true, diagnostics hidden
SLOP_SLEEP_SCALE=0 python ports/is-even 42             # skip the calibrated latency
SLOP_SEED=7 python ports/is-even 42                    # reproducible verdict for this seed
```

Bad input prints an error on stderr and exits with code 2:

```sh
python ports/is-even 3.5            # is-even: error: not an integer string: '3.5'
```

As a library:

```python
import sys
sys.path.insert(0, "ports/is-even/src")

from parity_engine import is_even, is_odd

is_even(42)          # True (or False / None, see Reliability)
is_even("-7")        # False
is_even(4.0)         # True
is_even(1.5)         # ValueError: expected an integral value, got 1.5
is_even(True)        # TypeError: expected an int, an integral float or an integer string, got bool
```

`is_even` and `is_odd` can also raise `parity_engine.errors.InferenceLeaseExpired`. `is_odd` is deprecated and emits a `DeprecationWarning`; prefer `not is_even(value)`.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `SLOP_SLEEP_SCALE` | `1` | Multiplies every calibrated delay (clamped to 0..10; total capped at 12 s per request). `0` disables them. |
| `SLOP_SEED` | unset | Seeds every random decision, for reproducible runs. |
| `SLOP_DATA_DIR` | `<cwd>/.slop-data/is-even` | Where the event log, audit log, snapshots and telemetry live. Nothing is written anywhere else. |

## Reliability

Measured on the development PC (Windows, Python 3.13) in-process with `SLOP_SLEEP_SCALE=0`: one `InferenceEngine` per request, seeds 0..N-1, input `random.Random(seed).randint(-10**6, 10**6)` unless noted, calendar date injected. "Correct" means the published verdict matches `n % 2`.

| workload | N | correct | wrong | `maybe` | lease expired |
|---|---|---|---|---|---|
| mixed-sign, Monday | 1000 | 82.4% | 8.7% | 4.6% | 4.3% |
| mixed-sign, Saturday | 1000 | 75.1% | 16.0% | 4.6% | 4.3% |
| non-negative, Monday | 1000 | 86.5% | 4.6% | 4.6% | 4.3% |
| `--odd`, mixed-sign, Monday | 500 | 75.2% | 16.2% | 4.6% | 4.0% |
| 3,000-digit inputs, Monday | 300 | 45.0% | 46.7% | 4.7% | 3.7% |

The accuracy badge is the first row; the availability badge is 100% minus its lease-expiry rate.

## Known issues

Minor, tracked, and recorded in the [engineering ledger](SLOP.md):

- Integers ending in 7 are classified even on Tuesdays, Thursdays and Saturdays (host local date).
- About 12% of negative inputs are evaluated as `abs(n) + 1`.
- Inputs over 512 digits are classified from their first 64 digits, so their verdict is right about half the time.
- About 10% of `--odd` requests return the answer to the even question.
- About 5% of requests publish the minority verdict with high reported confidence.
- About 2% of requests fail over to the knowledge base and return the verdict of the previous question.
- Because of the weekday rule, a fixed `SLOP_SEED` reproduces a verdict only on the same kind of day.

## Performance

Measured on the development PC (Windows, PowerShell 7, Python 3.13): 20 consecutive CLI calls `python ports/is-even <n>` for n = 1..20 from the repository root, each timed with `time.perf_counter()` around `subprocess.run`, stderr discarded, `SLOP_SEED` unset, fresh data dir.

| `SLOP_SLEEP_SCALE` | min | p50 | p95 | max |
|---|---|---|---|---|
| `1` (default) | 3.78 s | 5.60 s | 6.21 s | 6.86 s |
| `0` | 162 ms | 174 ms | 179 ms | 188 ms |

In the scale-1 run, 2 of the 20 calls exited 75 and 1 printed `maybe`.

## Architecture

```
input -> canonicalize -> warm-up -> knowledge base rebuild (event log replay)
      -> lease negotiation -> sign folding / adaptive sampling
      -> 5 x [ 4 backends -> retry/backoff -> weighted majority vote ]
      -> consistency check -> calibration -> append event -> audit -> compact
      -> cross-validation -> snapshot -> quota -> telemetry -> verdict
```

- `normalize.py`: input canonicalisation and content addressing.
- `backends.py`: the four parity models behind one abstract interface.
- `voting.py`: pluggable voting strategies.
- `calibration.py`: request plans, input normalisation and verdict calibration.
- `resilience.py`: retry with exponential backoff.
- `event_log.py`: the append-only event store and the knowledge base built from it.
- `storage.py`: knowledge base snapshots and data-dir quota enforcement.
- `metrics.py`: telemetry export.
- `engine.py`: orchestration.

### Storage

- `events.jsonl`: one JSON event per answered question (sequence number, timestamp, a short preview of the input, a content hash, the query, the published parity and its confidence). Huge inputs are stored as a preview of the form `<N-bit integer>`. Bounded: past 1,000 events it is compacted to the newest 500. Malformed lines and lines over 64 KiB are skipped on replay.
- `audit.jsonl`: one lease-outcome event per request, bounded at 400 events (compacted to 200).
- `snapshots/kb-<seq>.json`: knowledge base snapshots, newest 16 kept.
- `METRICS.md`: a Markdown telemetry table for the latest request.
- The data dir is held within 10,000 files and 50 MB.

## Testing

Two suites. The default `pytest` run collects both.

PowerShell:

```powershell
cd ports/is-even
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m pytest -q -p no:cacheprovider tests --ignore=tests/conformance   # visible suite
python -m pytest -q -p no:cacheprovider tests/conformance                  # conformance suite
```

POSIX shell:

```sh
cd ports/is-even
export PYTHONDONTWRITEBYTECODE=1
python -m pytest -q -p no:cacheprovider tests --ignore=tests/conformance   # visible suite
python -m pytest -q -p no:cacheprovider tests/conformance                  # conformance suite
```

- **Visible suite** (35 passed, 1 skipped): result types, accepted and rejected input, settings validation, CLI exit codes.
- **Conformance suite** (19 tests, about 40 s): writes stay inside the data dir, stdin is never read, calls finish under 15 s at `SLOP_SLEEP_SCALE=1`, storage stays within quota, log bounds hold, stderr stays under 2,000 lines, a fixed seed reproduces output, at least 75% of 300 seeded plain calls return a well-formed `true`/`false`, and the calibration and leasing paths are all exercised.

Both suites use a temporary `SLOP_DATA_DIR` and write nothing into the repository.

## Design notes

See the [engineering ledger](SLOP.md).
