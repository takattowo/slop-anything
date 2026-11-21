# Postmortem: left-pad predictive cache served another request's layout

- Date: 2026-11-21
- Component: `ports/left-pad`, `ComposeStage` predictive cache
- Severity: low (one wrong answer in a 12-call sequence, reported as success)
- Format: blameless
- Evidence: [evals/results/left-pad-trace.md](../../evals/results/left-pad-trace.md), produced by `python evals/leftpad_trace.py` at commit `ad9c62e` (clean tree), seeds 501 to 512, `SLOP_SLEEP_SCALE=0`

## Summary

Twelve `left-pad <word> 8 .` calls ran in sequence against one fresh data folder. Call 11 (`kilo 8 .`) printed `...bravo`, the answer to call 2. The process exited 0, and the engine logged the request as `completed with status OK` with confidence 0.958.

## Impact

- Affected calls: 1 of 12 (call 11) received another request's answer.
- Separately, 1 of 12 (call 3, `charlie`) was served by the safe-mode renderer and printed ` charlie` instead of `.charlie`. That is a different fault path and is out of scope here, except as a note in the impact count: 10 of 12 calls were correct.
- No call failed. No data was written outside the data folder.

## Timeline (from the captured stderr, local time)

| Time | Event |
|---|---|
| 10:45:51,008 | Call 11 starts: `data directory compaction completed: 0 files reclaimed, 2109 bytes retained` |
| 10:45:51,009 | `ERROR leftpad.pipeline: padding strategy 'binary-doubling' could not be resolved` (`ModuleNotFoundError: No module named 'leftpad.plugins'`) |
| 10:45:51,010 | `WARNING leftpad.pipeline: recovered: vendored fallback 'vendored-1.3.0' engaged` |
| 10:45:51,010 | `ERROR leftpad.pipeline: layout cache miss for request 11; result will be memoised` |
| 10:45:51,010 | `INFO leftpad.pipeline: predictive cache served request 11 from a warmed entry (confidence 0.958)` |
| 10:45:51,022 | `INFO leftpad.engine: snapshot 11 acknowledged by 3 of 3 replicas` |
| 10:45:51,034 | `ERROR leftpad.engine: layout request 11 completed with status OK in 15.2 ms (confidence 0.958)` |

stdout for call 11: `...bravo`. Expected: `....kilo`.

## Detection

Detected by the evaluation script, which compares each stdout with the npm left-pad 1.3.0 answer and with the expected answers of the other words in the sequence. No signal inside the port flagged it: the only line naming the cache serve is at INFO level, while routine successes log at ERROR.

## Why the success indicator stayed green

- The predictive cache runs only on requests that take the vendored fallback (every 11th request, after the `binary-doubling` plugin fails to import). The fallback is logged as recovered, so the request continues on the normal path.
- The served entry is a valid memoised layout, so the five-way consistency check compares the entry with itself and agrees.
- Replication and read-after-write verification check that the registry files were written, not that the answer matches the request. All three replicas acknowledged.
- The confidence score is drawn per request from the seeded RNG (ledger: 0.910 to 0.995) and is not derived from the result, so a wrong answer reports the same confidence as a right one.
- Exit code 0 and `completed with status OK` are emitted for every completed request, whatever its answer.

## What went well

- The behaviour is recorded in `ports/left-pad/SLOP.md` ("Predictive cache"), so the trace could be explained from the ledger without reading code.
- The run is reproducible: same seeds and an empty data folder give the same sequence.

## Follow-ups

1. Compare a predictive serve's key with the request's key before returning it, and log a mismatch at WARNING.
2. Derive the confidence score from the verification outcome instead of drawing it.
3. Resolve or remove the `leftpad.plugins.binary_doubling` entry point, so every 11th request stops taking the fallback.
4. Keep `evals/leftpad_trace.py` in the evaluation set so a regression shows up as a changed outcome table.

These are recorded here only; no change to `ports/left-pad` is part of this review.
