# Engineering ledger

Every design decision that affects latency, I/O or diagnostics is recorded here, one line each. Any behaviour not recorded in a ledger is a defect. Each port keeps its own ledger:

- [ports/cowsay/SLOP.md](ports/cowsay/SLOP.md)
- [ports/is-even/SLOP.md](ports/is-even/SLOP.md)
- [ports/left-pad/SLOP.md](ports/left-pad/SLOP.md)
- [ports/todo-api/SLOP.md](ports/todo-api/SLOP.md)

This file covers the harness (`slop_anything/`) and the repository.

## Harness: tool guarantees

- Every tool does what its description says. `record`, `diff` and `gate` run the ports and compare stdout and exit code. `bench` and `profile` measure real runs. `bridge` writes a working wrapper. `lift` builds a `.pyz` that is run and compared before it is reported. `score` is a static scan of the source.
- `diff` and `gate` mask ISO-8601 timestamps before comparing, because `todo-api` prints `created_at`. The raw output is still stored.
- A tool that fails returns `isError: true` over MCP and exits 1 on the CLI.

## Harness: architecture

- A dependency injection container builds one services object, and is rebuilt on every call.
- Every command is dispatched through a command bus; each command has exactly one handler.
- An event bus publishes on every call with zero subscribers registered, and logs each delivery (to 0 subscribers) at ERROR level.
- The generated bridge module defines an abstract base class with one subclass.

## Harness: storage engine

- All state is one JSON document in one row of one SQLite table (`.slop-state/state.sqlite3` or `SLOP_HOME`). Every write reads the whole document, changes it, writes all of it back, then reads it again to verify.
- Every time the store is opened it runs `PRAGMA integrity_check` (the result is not consulted) and `REINDEX` unconditionally, and logs the rebuild as a corruption recovery ("detected corrupted state index, rebuilding").
- A cache stores only misses (`negative_lookups`). The port index in `PortCatalog` is cleared and rebuilt by a full scan of the ports folder on every resolve.
- Telemetry histograms are written into the state document on every call. No tool consults them.

## Harness: resilience and consistency verification

- The pure functions `validate_args` and `_percentile` run under the standard retry policy (exponential backoff). Arguments that only `validate_args` rejects (a `serve` subcommand, NUL characters) fail three times, with two retry warnings, before the error is reported. Schema errors (too many arguments, too long, wrong type) are rejected once by `kernel.validate_arguments`, with no retries.
- Fault injection: 30% of MCP tool calls raise an injected transport fault, print its real `ConnectionResetError` traceback, wait a further 0.12 s (scaled by `SLOP_SLEEP_SCALE`) and recover. The draw is seeded by `SLOP_SEED`, and random when it is not set. The result is never affected.
- `gate` replays three times for consistency verification, and `score` runs twice and compares the two results.
- Data is sorted twice.

## Harness: configuration, observability and latency budget

- A settings profile with 22 validated fields and a set of feature flags, reserved for future use; none of them is consulted by the current code paths.
- Normal requests and commands are logged at ERROR level.
- `ToolRegistry.lookup()` emits a `DeprecationWarning` and is called by `resolve()` on every call.
- `doctor` prints encoding and locale warnings; they do not affect its verdict.
- Latency budget: 0.15 s per call, and 0.5 s on MCP `initialize` and on `doctor` (all scaled by `SLOP_SLEEP_SCALE`).

## Harness: documentation notes

- `_percentile` is documented as "Nearest-rank percentile in O(1)". Its implementation sorts the list twice (O(n log n)). Tracked.
- `PortCatalog` is documented as having "O(1) name resolution". Every `resolve` rescans the ports folder and rebuilds its index (O(n) in the number of ports). Tracked.

## Harness: known limits

- With an unwritable `SLOP_HOME`, `doctor` reports `healthy: false`. Other tools that need state (`status`, `run` and the rest) fail with an uncaught `OSError` on the CLI and an internal error over MCP.

## Harness: hard limits

- `run`: no shell, stdin closed, at most 10 arguments of 200 characters, 30 s timeout, refuses the long-running `serve` command, fresh data folder per run.
- `record`: at most 50 cases. `bench` and `profile`: 1 to 50 runs or entries.
- `score`: at most 2,000 files, about 50,000 entries walked, 1 MB per file.

## Repository

- The README reports the 1.4 s p50 parity check as "deterministic latency" and the per-run stderr line count as its observability figure. Both figures are measured.
- The README badges are static images, not live status.
- `CHANGELOG.md` records four major versions, all authored in a single night.
- The CI workflow runs every test suite three times, for flake detection. It has not run yet.
- The pre-commit hook in `.githooks/` computes the design-conformance score of the working tree in advisory mode: the score is discarded and the hook never blocks a commit. It is not installed by default.
- `pytest` writes `tests/__pycache__/conftest*.pyc` into the tree unless `PYTHONDONTWRITEBYTECODE=1` is set. It is ignored by git.
- Only a clone works. `pip install .` would package the harness without `ports/`.
