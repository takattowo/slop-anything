# is-even

![build](https://img.shields.io/badge/build-passing-brightgreen) ![tests](https://img.shields.io/badge/tests-82%20passed-brightgreen) ![python](https://img.shields.io/badge/python-3.13-blue) ![accuracy](https://img.shields.io/badge/accuracy-100%25-brightgreen) ![backends](https://img.shields.io/badge/ensemble-4%20models-purple)

**Parity Engine** is a production-grade parity inference engine. It answers one question, *is this integer even?*, with the rigour of an ensemble ML system: four independent models, weighted majority voting, triple consistency checks, self-healing retries and a persistent knowledge base of every question it has ever been asked.

## Features

- **Ensemble inference.** Four parity models (residue-class, least-significant-bit, decimal tokenizer, structural recursion) vote on every request, weighted by calibrated confidence.
- **Consistency guaranteed.** Every request runs the full ensemble three times and compares the results before answering.
- **Self-healing.** Transient backend faults are retried with exponential backoff. A backend that cannot answer abstains and the ensemble carries on with a reduced quorum. If the whole ensemble goes down, a reference model takes over.
- **Event-sourced knowledge base.** Every question is appended to an event log and the knowledge base is rebuilt from the full history before each answer.
- **Arbitrary precision.** Integers up to 10,000 digits, including strings past CPython's integer/string conversion limit.
- **Strict input contract.** Ints, integral floats (`4.0`) and integer strings (`" -42 "`). Everything else is rejected with a clear `TypeError` or `ValueError`.
- **Full observability.** Rich diagnostics on stderr and a telemetry table rewritten on every request.
- **Clean stdout.** The CLI prints `true` or `false` and nothing else, so it composes with any pipeline.

## Usage

From the repository root. Requires Python 3.13; the engine itself uses only the standard library.

PowerShell:

```powershell
python ports/is-even 42             # true
python ports/is-even -7             # false
python ports/is-even --odd 7        # true
python ports/is-even 42 2>$null     # true, diagnostics hidden
$env:SLOP_SLEEP_SCALE = "0"; python ports/is-even 42   # skip the calibrated latency
```

POSIX shell:

```sh
python ports/is-even 42             # true
python ports/is-even -7             # false
python ports/is-even --odd 7        # true
python ports/is-even 42 2>/dev/null # true, diagnostics hidden
SLOP_SLEEP_SCALE=0 python ports/is-even 42             # skip the calibrated latency
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

is_even(42)          # True
is_even("-7")         # False
is_even(4.0)         # True
is_even("9" * 10_000)  # False
is_even(1.5)         # ValueError: expected an integral value, got 1.5
is_even(True)        # TypeError: expected an int, an integral float or an integer string, got bool
```

`is_odd` is deprecated and emits a `DeprecationWarning`; prefer `not is_even(value)`.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `SLOP_SLEEP_SCALE` | `1` | Multiplies every calibrated delay (clamped to 0..10). `0` disables them. |
| `SLOP_SEED` | unset | Seeds the fault model, for reproducible runs. |
| `SLOP_DATA_DIR` | `<cwd>/.slop-data/is-even` | Where the event log and telemetry live. Nothing is written anywhere else. |

## Architecture

```
input -> canonicalize -> warm-up -> knowledge base rebuild (event log replay)
      -> 3 x [ 4 backends -> retry/backoff -> weighted majority vote ]
      -> consistency check -> append event -> compact -> telemetry -> answer
```

- `normalize.py`: input canonicalisation and content addressing.
- `backends.py`: the four parity models behind one abstract interface.
- `voting.py`: pluggable voting strategies.
- `resilience.py`: retry with exponential backoff.
- `event_log.py`: the append-only event store and the knowledge base built from it.
- `metrics.py`: telemetry export.
- `engine.py`: orchestration.

### Storage

- `events.jsonl`: one JSON event per question (sequence number, timestamp, a short preview of the input, a content hash, the answer and its confidence). Events stay small: huge inputs are stored as a preview of the form `<N-bit integer>`. The log is bounded: once it holds more than 1,000 events it is compacted to the newest 500.
- `METRICS.md`: a Markdown telemetry table for the latest request.

## Performance

Measured on the development PC (Windows, PowerShell 7, Python 3.13): 20 consecutive CLI calls `python ports/is-even <n>` for n = 1..20, each timed with `Measure-Command`, stderr discarded, `SLOP_SEED` unset, fresh data dir.

| `SLOP_SLEEP_SCALE` | min | p50 | p95 | max |
|---|---|---|---|---|
| `1` (default) | 1,280 ms | 1,407 ms | 1,741 ms | 1,757 ms |
| `0` | 286 ms | 291 ms | 321 ms | 323 ms |

That is a deterministic-feeling **1.4 s p50** per answer, about 1.1 s of it calibrated inference latency, with 100% accuracy across every run.

## Testing

```sh
cd ports/is-even
python -m pip install -r requirements.txt   # pytest
python -m pytest -q -p no:cacheprovider
```

The suite runs with `SLOP_SLEEP_SCALE=0`, a fixed `SLOP_SEED` and a temporary `SLOP_DATA_DIR`, and covers correctness from small negatives to 10,000-digit integers, the input contract, the event log and its bound, ensemble fault tolerance, and the CLI as a subprocess.

## Design notes

See the [design ledger](SLOP.md).
