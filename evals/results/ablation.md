# Ablation: one backend vs the full quorum (calc)

- Commit: `ad9c62efb45ad198055a18a7e9ac4e06362c709e`
- Measured code: `clean at that commit`
- Python: `3.13.14`
- Platform: `win32`
- Measured at: `2026-11-21T03:45:48Z`
- Cases: `26 x 4 rounds = 104 calls per configuration`
- Sleep scale: `0`

## How this was measured

- In-process, through `ArithmeticInferenceService(backends=[...], data_dir=...)`, the constructor argument the calc package exposes. No file under `ports/` was changed and nothing was monkeypatched.
- Same case file and seeds as the leaderboard (call k uses `SLOP_SEED=k`), `SLOP_SLEEP_SCALE=0`, one fresh data folder per round and configuration.
- Correct: the served text, read as a rational number, equals the expected value. Failed: the request raised a `CalcError` (consensus timeout).
- "Wrong became right" and "right became wrong" compare each call with the same call (round, case) under the full quorum.
- Time: `time.perf_counter()` around each `compute()` call, summed; no interpreter start is included.

## Result

Replacing the four-backend quorum with `exact-ast` alone: 5 wrong or failed answers became right, 0 right answers became wrong or failed, 85 / 104 correct vs 80 / 104, 695.4 ms vs 735.4 ms in-process.

| Configuration | Correct | Wrong | Failed | Wrong became right | Right became wrong | Time (all calls) | stderr lines |
|---|---|---|---|---|---|---|---|
| full quorum (4 backends) | 80 / 104 | 21 | 3 | n/a (reference) | n/a (reference) | 735.4 ms | 2884 |
| single backend: `exact-ast` | 85 / 104 | 16 | 3 | 5 | 0 | 695.4 ms | 2241 |
| single backend: `ieee754-float` | 75 / 104 | 26 | 3 | 0 | 5 | 709.1 ms | 2241 |
| single backend: `neural-estimator` | 78 / 104 | 23 | 3 | 4 | 6 | 714.3 ms | 2243 |
| single backend: `distributed-shard` | 83 / 104 | 18 | 3 | 5 | 2 | 825.6 ms | 2241 |

Cases still wrong with `exact-ast` alone (finalisation runs after the vote, so the backend set does not reach it): `mul-4x14`, `mul-7x8`, `mul-8x7`, `pow-64`, `square-12`, `sub`.
