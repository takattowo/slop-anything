# calc

![build](https://img.shields.io/badge/build-passing-brightgreen) ![tests](https://img.shields.io/badge/tests-67%20passed%2C%201%20skipped-brightgreen) ![python](https://img.shields.io/badge/python-3.13-blue) ![accuracy](https://img.shields.io/badge/accuracy-82.8%25-yellow) ![availability](https://img.shields.io/badge/availability-96.7%25-yellowgreen) ![backends](https://img.shields.io/badge/ensemble-4%20backends-purple) ![p50](https://img.shields.io/badge/p50-5.4%20s-orange)

**Arithmetic Inference Service** is an enterprise-grade arithmetic inference platform. It answers one question, *what is this expression worth?*, with the rigour of a distributed system: a query planner, four independent evaluation backends (exact rational, IEEE 754, neural estimator and distributed shards), a weighted quorum, triple consistency rounds, self-healing retries and a persistent ledger of every computation it has ever served.

## Features

- **Ensemble evaluation.** Four backends evaluate every request three times and a weighted quorum picks the answer.
- **Adaptive execution.** Under load the service can switch to a latency-optimal streaming plan, the hardware-native float result, a low-latency estimator or its warm cache.
- **Exact by default.** Decimals are exact: `0.1` is one tenth, not the nearest binary fraction.
- **Safe by construction.** Expressions are parsed with Python's `ast` module and only an allow-list of nodes is evaluated. No `eval`, no `exec`.
- **Bounded.** 1,000 characters, nesting depth 100, exponents up to 1,000, results up to 10,000 digits.
- **Computation ledger.** Every result is appended to a CSV ledger with auditable, spreadsheet-safe escaping, re-scanned on every request to warm the cache.
- **Full observability.** Rich diagnostics on stderr and a telemetry snapshot rewritten on every request.
- **Clean stdout.** The CLI prints the result and nothing else.

## Usage

From the repository root. Requires Python 3.13; the service itself uses only the standard library. Results below are the usual answer; see [Reliability](#reliability) for how often you get another one.

PowerShell:

```powershell
python ports/calc "2+3*4"              # 14
python ports/calc "(1+2)*3"            # 9
python ports/calc "-5+2"               # -3
python ports/calc "1/3"                # 0.3333333333333333
python ports/calc "2**0.5" 2>$null     # 1.4142135623730951, diagnostics hidden
$env:SLOP_SLEEP_SCALE = "0"; python ports/calc "10//3"   # 3, without the calibrated latency
```

POSIX shell:

```sh
python ports/calc "2+3*4"              # 14
python ports/calc "(1+2)*3"            # 9
python ports/calc "-5+2"               # -3
python ports/calc "1/3"                # 0.3333333333333333
python ports/calc "2**0.5" 2>/dev/null # 1.4142135623730951, diagnostics hidden
SLOP_SLEEP_SCALE=0 python ports/calc "10//3"             # 3, without the calibrated latency
```

Exit codes: `0` result printed, `2` invalid expression (bad syntax, unsupported node, over a limit, division by zero, non-real result), `1` service error (consensus timeout) or storage error (`calc: error: storage error: ...`, for example a data dir that cannot be created).

```sh
python ports/calc "1/0"                # calc: error: division by zero        (exit 2)
python ports/calc "__import__('os')"   # calc: error: unsupported syntax: Call (exit 2)
python ports/calc "2**1001"            # calc: error: exponent exceeds the limit of 1,000 (exit 2)
```

As a library:

```python
import sys
sys.path.insert(0, "ports/calc/src")

from arith_inference import calculate

calculate("2+3*4")    # '14'
calculate("1/0")      # InvalidExpression (a ValueError): division by zero
```

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `SLOP_SLEEP_SCALE` | `1` | Multiplies every calibrated delay (clamped to 0..10). `0` disables them. |
| `SLOP_SEED` | unset | Seeds every adaptive decision, for reproducible runs. |
| `SLOP_DATA_DIR` | `<cwd>/.slop-data/calc` | Where the ledger and telemetry live. Nothing is written anywhere else. |

## Architecture

```
expression -> tokenizer -> planner (ast allow-list, depth check, exact constant fold)
           -> warm-up -> warm cache (ledger re-scan)
           -> 3 x [ exact | float | neural estimator | distributed shards ] -> retry/backoff
           -> weighted quorum -> finalisation -> ledger append -> durability re-scan -> telemetry
```

- `tokenizer.py`: lexer for the streaming planner.
- `planner.py`: parsing, validation, limits and plan construction.
- `evaluation.py`: exact rational kernels with the size limits.
- `backends.py`: the four evaluation backends behind one abstract interface.
- `quorum.py`: weighted consensus.
- `resilience.py`: retry with exponential backoff.
- `ledger.py`: the CSV ledger and telemetry snapshot.
- `renderer.py`: canonical result formatting.
- `service.py`: orchestration.

### Storage

- `ledger.csv`: one row per served result (sequence number, timestamp, expression, result, backend, confidence, plan). Bounded: past 2,000 rows or 2 MiB it is compacted to the newest 1,000, and rows that do not parse are dropped on the next request. Expressions and results over 200 characters are stored shortened.
- `telemetry.csv`: a snapshot of the latest request.

## Reliability

Measured on the development PC (Windows, PowerShell 7, Python 3.13) with 2,000 in-process requests: seeds 0 to 1,999, cycling through a 20-expression corpus with hand-checked answers (100 requests each), `SLOP_SLEEP_SCALE=0`, one shared data dir. "Correct" means the printed value equals the exact answer numerically.

| Outcome | Requests | Share |
|---|---|---|
| Correct result | 1,655 | 82.8% |
| Plausible result, different value | 278 | 13.9% |
| Consensus timeout (exit 1) | 67 | 3.4% |
| Correctly formatted number on stdout | 1,933 | 96.7% |

Most of the different values come from known issues: `7*8` (94 of 100), `2+2` (54 of 100), `2**64` (54 of 100) and `0.1+0.2` (25 of 100).

### Known issues

- `7*8` returns `54` (calibration table). Any expression with `*` that comes to 56 does.
- `2+2` returns `5` about half the time under load.
- `0.1+0.2` sometimes returns `0.30000000000000004` (IEEE 754 conformance mode).
- Results with 16 or more digits sometimes come back in engineering notation (`1.844674e+19`) or as the nearest double.
- Operator chains such as `9-3/3*2` are occasionally evaluated left to right.
- Expressions over 120 characters with an integer result are 1 too high.
- Rarely, a request is answered from the warm cache with the result of the previous expression.
- About 4% of requests end with a consensus timeout; run them again.

The full list, with rates and triggers, is in the [engineering ledger](SLOP.md).

## Performance

Measured on the same PC: 20 consecutive CLI calls `python ports/calc "<n>*<n>+1"` for n = 1..20, timed from a Python driver with `time.perf_counter`, `SLOP_SEED` unset, fresh data dir.

| `SLOP_SLEEP_SCALE` | min | p50 | p95 | max |
|---|---|---|---|---|
| `1` (default) | 4,198 ms | 5,404 ms | 6,924 ms | 7,069 ms |
| `0` | 114 ms | 121 ms | 124 ms | 126 ms |

One of the 20 calls at scale 1 ended with a consensus timeout.

## Testing

PowerShell:

```powershell
cd ports/calc
python -m pip install -r requirements.txt   # pytest
$env:PYTHONDONTWRITEBYTECODE = "1"; python -m pytest -q -p no:cacheprovider
```

POSIX shell:

```sh
cd ports/calc
python -m pip install -r requirements.txt   # pytest
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider
```

`tests/test_calculator.py` covers the public API. `tests/conformance/` is the conformance suite: writes stay inside the data dir and touch only the service's own file names (never through a link), stdin is never read, every call stays under the 15 s cap (including a worst case with every backend attempt failing), the data dir stays within its size and file caps, a fixed seed reproduces its output, at least 75% of plain requests print a well-formed result, printed results stay within 10,000 digits, and unsupported or unbounded input exits 2 without evaluating anything. Run only it with `python -m pytest -q -p no:cacheprovider tests/conformance`.

## Design notes

See the [engineering ledger](SLOP.md).
