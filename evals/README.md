# Evaluations

Reproducible measurements of the ports and the harness. Every script uses the standard library only, runs offline, caps its own case count and run time, works in folders it creates with `tempfile.mkdtemp` and removes them by exact path, and runs ports as subprocesses with argument lists and stdin closed. Nothing is passed to `eval` or `exec`. Each results file records the commit it measured, whether `ports/`, `slop_anything/` and `tests/` were clean at that commit, the Python version and the time.

| Script | What it measures | Results | Run time (development machine) |
|---|---|---|---|
| [`golden/run_golden.py`](golden/run_golden.py) | One `calc "7*8"` call at `SLOP_SLEEP_SCALE=1`, seed 7, saved as a full transcript | [`golden/calc-7x8.txt`](golden/calc-7x8.txt) | about 6 s |
| [`leaderboard.py`](leaderboard.py) | `calc` vs a plain Python `operator` baseline on the [published case set](cases/arithmetic.json): correct/total, batch wall time, the harness's projected speedup (not observed) | [`results/leaderboard.md`](results/leaderboard.md) | about 35 s |
| [`ablation.py`](ablation.py) | `calc` with one backend vs the four-backend quorum, same cases and seeds | [`results/ablation.md`](results/ablation.md) | about 10 s |
| [`pilot_monday_cohort.py`](pilot_monday_cohort.py) | Internal synthetic pilot: 5 todos created with the clock on a Monday (UTC) | [`results/pilot_monday_cohort.md`](results/pilot_monday_cohort.md) | about 2 s |
| [`leftpad_trace.py`](leftpad_trace.py) | 12 left-pad calls in one data folder, for the predictive-cache postmortem | [`results/left-pad-trace.md`](results/left-pad-trace.md) | about 5 s |
| [`mcp_readiness.py`](mcp_readiness.py) | 150 distinguishable `tools/call` requests over stdio: protocol success vs response belongs to its request | [`results/mcp_readiness.md`](results/mcp_readiness.md) | about 20 s |

The postmortem built from the left-pad trace is [docs/postmortems/2026-11-21-left-pad-predictive-cache.md](../docs/postmortems/2026-11-21-left-pad-predictive-cache.md).

## Running

Run from the repository root. Each script prints one summary line and rewrites its results file.

PowerShell:

```
$env:PYTHONDONTWRITEBYTECODE='1'
python evals/golden/run_golden.py
python evals/leaderboard.py
python evals/ablation.py
python evals/pilot_monday_cohort.py
python evals/leftpad_trace.py
python evals/mcp_readiness.py
```

POSIX:

```
export PYTHONDONTWRITEBYTECODE=1
python evals/golden/run_golden.py
python evals/leaderboard.py
python evals/ablation.py
python evals/pilot_monday_cohort.py
python evals/leftpad_trace.py
python evals/mcp_readiness.py
```

Options: `leaderboard.py` and `ablation.py` take `--rounds N` (1 to 10, default 4); `mcp_readiness.py` takes `--calls N` (100 to 200, default 150). `pilot_monday_cohort.py` needs Flask installed, like the `todo-api` port.

## Notes

- Seeds are fixed in each script, so a rerun on the same commit gives the same answers. Timings and timestamps differ between runs.
- Exception: `mcp_readiness.py` is not reproducible run to run: its outcome does not depend on the seed alone. Two runs with seed 1234 on the same `ports/` and `slop_anything/` code gave 134 / 150 and 139 / 150 replies that belonged to their request (protocol success 150 / 150 both times). The committed results file is the first run.
- `ablation.py` and `pilot_monday_cohort.py` import the port packages in-process. The ablation passes its backend list through the `ArithmeticInferenceService(backends=...)` constructor argument. The pilot patches `todo_api.service.utc_now` inside its own process, because the CLI has no supported way to pin the clock. No port file is changed.
- Quoted diagnostics show machine-specific folders as `<repo>`, `<tmp>`, `<python>` and `~`. Nothing else in a captured output is changed.
- The projected speedup in the leaderboard comes from `python -m slop_anything bench`. The harness ledger states it is not measured; it is reported as given and labelled "not observed".
