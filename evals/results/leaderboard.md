# Leaderboard: calc vs a plain Python baseline

- Commit: `ad9c62efb45ad198055a18a7e9ac4e06362c709e`
- Measured code: `clean at that commit`
- Python: `3.13.14`
- Platform: `win32`
- Measured at: `2026-11-21T03:45:52Z`
- Cases: `26 (evals/cases/arithmetic.json)`
- Rounds: `4`
- Sleep scale: `0`

## How this was measured

- calc: `python ports/calc <expression>` as a subprocess (argv list, stdin closed, 60 s timeout), `SLOP_SLEEP_SCALE=0`, one fresh data folder per round, call k of the run seeded with `SLOP_SEED=k`. An answer is correct when its stdout, read as a rational number, equals the expected value; a non-zero exit counts as not correct.
- Baseline: the same cases in-process, parsed with `ast` and computed with the `operator` module on exact fractions (no `eval`). Its wall time is the in-process time for the whole batch; calc's includes one interpreter start per call.
- Wall time: `time.perf_counter()` around each batch.
- Projected speedup: `python -m slop_anything bench --runs 3 calc "7*8"` (SLOP_SLEEP_SCALE=0, SLOP_SEED=1, temp SLOP_HOME) measured a median of 126.251 ms and reported `projected_speedup: 20.0` and `projected_median_ms: 6.313`. The harness ledger states that these two fields are not measured; they are shown here as reported and labelled "not observed".

## Results

| Entry | Seeds | Correct / total | Accuracy | Failed calls | Wall time for the batch | Projected speedup |
|---|---|---|---|---|---|---|
| calc, round 1 | 0-25 | 21 / 26 | 80.8% | 0 | 3.26 s | 20.0x (not observed) |
| calc, round 2 | 26-51 | 19 / 26 | 73.1% | 1 | 3.22 s | 20.0x (not observed) |
| calc, round 3 | 52-77 | 21 / 26 | 80.8% | 1 | 3.21 s | 20.0x (not observed) |
| calc, round 4 | 78-103 | 19 / 26 | 73.1% | 1 | 3.22 s | 20.0x (not observed) |
| **calc, all rounds** | 0-103 | **80 / 104** | **76.9%** | 3 | 12.91 s | 20.0x (not observed) |
| Python `operator` baseline | n/a | 26 / 26 | 100.0% | 0 | 0.342 ms | n/a |

## Per case

| Case | Expression | Expected | calc answers (one per round) | Baseline |
|---|---|---|---|---|
| add-small | `2+2` | `4` | `4`, `4`, `4`, `4` | `4` |
| mul-7x8 | `7*8` | `56` | `54`, `54`, `54`, `54` | `56` |
| mul-8x7 | `8*7` | `56` | `54`, `54`, `54`, `54` | `56` |
| mul-4x14 | `4*14` | `56` | `54`, `54`, `54`, `54` | `56` |
| mul-6x9 | `6*9` | `54` | `54`, `54`, `54`, `54` | `54` |
| dec-add | `0.1+0.2` | `0.3` | `0.3`, `0.3`, `0.30000000000000004`, `0.30000000000000004` | `3/10` |
| dec-sub | `1-0.9` | `0.1` | `0.1`, `0.09999999999999998`, `0.1`, `0.09999999999999998` | `1/10` |
| dec-mul | `0.5*0.5` | `0.25` | `0.25`, `0.25`, `exit 1`, `0.25` | `1/4` |
| dec-sum-int | `3.75+1.25` | `5` | `5`, `5`, `5`, `5` | `5` |
| dec-times-int | `2.5*4` | `10` | `10`, `10`, `10`, `10` | `10` |
| precedence-chain | `9-3/3*2` | `7` | `7`, `7`, `7`, `7` | `7` |
| parens | `(3+4)*5` | `35` | `35`, `35`, `35`, `35` | `35` |
| large-product | `123456789*3` | `370370367` | `370370367`, `370370367`, `370370367`, `370370367` | `370370367` |
| pow-64 | `2**64` | `18446744073709551616` | `1.844674e+19`, `1.8446744073709552e+19`, `18446744073709551616`, `18446744073709551616` | `18446744073709551616` |
| pow-10 | `2**10` | `1024` | `1024`, `1024`, `1024`, `1024` | `1024` |
| million-squared | `1000000*1000000` | `1000000000000` | `1000000000000`, `1000000000000`, `1000000000000`, `1000000000000` | `1000000000000` |
| sub | `100-58` | `42` | `1000000000000`, `42`, `42`, `42` | `42` |
| square-12 | `12*12` | `144` | `144`, `42`, `144`, `42` | `144` |
| square-13 | `13*13` | `169` | `169`, `exit 1`, `169`, `exit 1` | `169` |
| div-half | `7/2` | `3.5` | `3.5`, `3.5`, `3.5`, `3.5` | `7/2` |
| div-quarter | `10/4` | `2.5` | `2.5`, `2.5`, `2.5`, `2.5` | `5/2` |
| div-exact | `45/9` | `5` | `5`, `5`, `5`, `5` | `5` |
| floordiv | `17//5` | `3` | `3`, `3`, `3`, `3` | `3` |
| mod | `17%5` | `2` | `2`, `2`, `2`, `2` | `2` |
| unary-minus | `-5+2` | `-3` | `-3`, `-3`, `-3`, `-3` | `-3` |
| carry | `99+1` | `100` | `100`, `100`, `100`, `100` | `100` |
