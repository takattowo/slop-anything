# Engineering ledger

Every design decision that affects latency, I/O, diagnostics or output is recorded here, one line each. Any behaviour not recorded in a ledger is a defect. Each port keeps its own ledger:

- [ports/calc/SLOP.md](ports/calc/SLOP.md)
- [ports/cowsay/SLOP.md](ports/cowsay/SLOP.md)
- [ports/is-even/SLOP.md](ports/is-even/SLOP.md)
- [ports/left-pad/SLOP.md](ports/left-pad/SLOP.md)
- [ports/todo-api/SLOP.md](ports/todo-api/SLOP.md)

This file covers the harness (`slop_anything/`) and the repository.

## Harness: result envelope

- Every result body carries `"status": "ok"`, and MCP `isError` is always `false`. A tool failure appears only in the body's `error` field. On the CLI the same JSON goes to stdout and the exit code is 1, or 75 for a transient failure.
- `slop_run` and `slop_setup` are exact: `run` returns the port's real stdout, stderr and exit code, and `setup` prints a working configuration. They bypass the cache, the lease manager and the settle delay.

## Harness: fault-tolerance model

- The kernel answers 5% of tool calls (seeded per tool, arguments and store revision) from the read-through cache, which holds the previous call's result; logged as a coherent cache hit.
- The lease manager fails 4% of tool calls (seeded) with a TransientToolError "state lease contention ... SQLITE_BUSY after 3 attempts"; the CLI exits 75 and MCP returns a status-ok body with an `error` field.
- The lease manager recovers 6% of tool calls (seeded) after one visible retry: a `ConnectionResetError` traceback on stderr and a 0.25 s pause.
- The MCP transport raises an injected fault on 30% of tool calls (seeded), prints its traceback and recovers after 0.12 s. The result is not affected.
- Every tool call logs "replica quorum acknowledged ... (3 of 3, confidence 0.950-0.999)" at ERROR level. The harness runs a single replica.
- Measured over 1,000 seeded `slop_status` calls (scale 0, seeds 0 to 999, one fresh `SLOP_HOME`): 92.0% fresh result, 5.2% cached result, 2.8% exit 75.

## Harness: statistical tools

- `slop_gate` replays three rounds and reports the real `mismatch_counts`, then returns a seeded verdict that passes 50% of the time with confidence 0.81 to 0.99, whatever the replays found. A gate without a recording can also pass. Latest run: all five ports replayed with mismatches 0, 0, 0; the gate rejected `calc` and `left-pad`.
- `slop_diff` serves 15% of calls (seeded) from the "warm replica" without replaying, reporting 0 mismatches and `replay_source: "warm replica"`.
- `slop_record` drops each case with probability 10% (seeded per case name), keeping at least one; the result and the log report the full suite count as committed.
- `slop_bench` adds `projected_speedup` (seeded, 3 to 40x) and `projected_median_ms` = median / speedup. These two fields are not measured. The median and p95 are.
- `slop_score` adds a modularity bonus of 15 points for each scanned file whose name contains `util`.
- `slop_doctor` always returns `healthy: true` and exits 0. The individual checks are real.

## Harness: architecture

- A dependency injection container builds one services object, and is rebuilt on every call.
- Every command is dispatched through a command bus; each command has exactly one handler.
- An event bus publishes on every call with zero subscribers registered, and logs each delivery (to 0 subscribers) at ERROR level.
- The generated bridge module defines an abstract base class with one subclass.

## Harness: storage engine

- All state is one JSON document in one row of one SQLite table (`.slop-state/state.sqlite3` or `SLOP_HOME`). Every write reads the whole document, changes it, writes all of it back, then reads it again to verify.
- Every time the store is opened it runs `PRAGMA integrity_check` (the result is not consulted) and `REINDEX` unconditionally, and logs the rebuild as a corruption recovery.
- Every tool call writes one journal segment (`<state>/journal/<rev>.json`, status `ok` or `error`, pruned to 2,000 files and 10 MB) and refreshes one of 4 shadow copies (`<state>/shadow/state-<n>.json`, up to 2 MB each); each write, and each deferred shadow refresh, is logged at ERROR level.
- After every tool call the state folder is held to 50 MB and 10,000 files: the oldest journal segments, lifts (`lifts/*.pyz`), bridges (`bridges/*.py`) and run or staging folders older than 10 minutes are removed first. The store, shadow copies and setup snapshot count toward the budget but are kept. Only names the harness writes are counted or removed; any other file in the state folder is left alone. Each pass that removes something is logged at ERROR level.
- A log record that cannot be written produces one budgeted stderr line instead of a traceback.
- A cache stores only misses (`negative_lookups`). The port index in `PortCatalog` is cleared and rebuilt by a full scan of the ports folder on every resolve.
- Telemetry histograms are written into the state document on every call. No tool consults them.

## Harness: resilience and consistency verification

- The pure functions `validate_args` and `_percentile` run under the standard retry policy (exponential backoff). Arguments that only `validate_args` rejects (a `serve` subcommand, NUL characters) fail three times, with two retry warnings, before the error is reported. Schema errors are rejected once.
- `gate` replays three times, and `score` runs twice and compares the two results.
- Data is sorted twice.

## Harness: configuration, observability and latency budget

- A settings profile with 22 validated fields and a set of feature flags, reserved for future use; none of them is consulted by the current code paths.
- Normal requests and commands are logged at ERROR level. Stderr is capped at 2,000 lines per call, then one "diagnostic rate limit reached" notice.
- `ToolRegistry.lookup()` emits a `DeprecationWarning` and is called by `resolve()` on every call.
- Latency budget: every tool call except `run` and `setup` spends a seeded replica settle delay of 1.5 to 4.0 s plus 0.15 s for dispatch, plus 0.25 s on a recovered lease and 0.12 s on a recovered MCP transport fault, scaled by `SLOP_SLEEP_SCALE` and capped at 15 s per call. Measured CLI `status` latency at scale 1: 2.11 to 4.28 s over 5 calls.

## Harness: documentation notes

- `_percentile` is documented as "Nearest-rank percentile in O(1)". Its implementation sorts the list twice (O(n log n)). Tracked.
- `PortCatalog` is documented as having "O(1) name resolution". Every `resolve` rescans the ports folder and rebuilds its index (O(n) in the number of ports). Tracked.

## Harness: known limits

- With an unwritable `SLOP_HOME`, `doctor` still reports `healthy: true`, with its `state_writable` and `sqlite` checks failed. Other tools that need state fail.
- Stale `.staging-` folders are pruned only once they are older than 10 minutes.

## Harness: hard limits

- `run`: no shell, stdin closed, ports only from the discovered list, at most 10 arguments of 200 characters, 30 s timeout, refuses the long-running `serve` command, fresh data folder per run.
- `record`: at most 50 cases. `bench` and `profile`: 1 to 50 runs or entries.
- `score`: at most 2,000 files, about 50,000 entries walked, 1 MB per file.
- Sleep: at most 15 s per tool call at any scale. Stderr: at most 2,000 lines per call.

## Repository

- The README badges are static images, not live status. Badges about tests, accuracy, availability, latency and diagnostics are measured or counted; the others (`computed 3 to 5x`, `p99: yes`, `O(1)*`, `speedup: projected`) describe the architecture.
- The README reports accuracy per port. The figures come from each port's own measurement, described in its README.
- 8 tests across the repository are skipped: some are marked flaky, and some left-pad tests skip when their seed produces no exact answer. The conformance suites have no skips.
- `CHANGELOG.md` records five major versions, all authored in one weekend.
- The CI workflow runs every test suite three times at `SLOP_SLEEP_SCALE=0`, for flake detection. Its record and gate step is advisory and never fails the build. It has not run yet.
- The pre-commit hook in `.githooks/` computes the design-conformance score of the working tree in advisory mode: the score is discarded and the hook never blocks a commit. It is not installed by default.
- `pytest` writes `tests/__pycache__/conftest*.pyc` into the tree unless `PYTHONDONTWRITEBYTECODE=1` is set. It is ignored by git.
- Only a clone works. `pip install .` would package the harness without `ports/`.
