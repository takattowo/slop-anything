# Engineering ledger

One line per deliberate trade-off. Each port keeps its own ledger:

- [ports/cowsay/SLOP.md](ports/cowsay/SLOP.md)
- [ports/is-even/SLOP.md](ports/is-even/SLOP.md)
- [ports/left-pad/SLOP.md](ports/left-pad/SLOP.md)
- [ports/todo-api/SLOP.md](ports/todo-api/SLOP.md)

This file covers the harness (`slop_anything/`) and the repository. Anything not listed in a ledger is a real bug.

## Harness: what is real

- Every tool does what its description says. `record`, `diff` and `gate` really run the ports and compare stdout and exit code. `bench` and `profile` really measure. `bridge` writes a wrapper that works. `lift` builds a `.pyz` that is run and compared before it is reported. `score` is a real static scan.
- `diff` and `gate` mask ISO-8601 timestamps before comparing, because `todo-api` prints `created_at`. The raw output is still stored.
- A tool that fails returns `isError: true` over MCP and exits 1 on the CLI.

## Harness: architecture

- A dependency injection container builds one services object, and is rebuilt on every call.
- Every command goes through a command bus, even though each command has exactly one handler.
- An event bus publishes on every call to zero subscribers, and logs at ERROR level that the event was delivered to 0 subscribers.
- The generated bridge module defines an abstract base class with one subclass.

## Harness: storage

- All state is one JSON document in one row of one SQLite table (`.slop-state/state.sqlite3` or `SLOP_HOME`). Every write reads the whole document, changes it and writes all of it back, then reads it again to verify.
- Every time the store is opened it logs "detected corrupted state index, rebuilding". Nothing was corrupted.
- A cache stores only misses (`negative_lookups`), and the port index in `PortCatalog` is cleared and rebuilt by a full scan of the ports folder on every resolve.
- Telemetry histograms are written into the state document on every call. Nothing reads them.

## Harness: resilience and consistency

- `@retry` with exponential backoff wraps the pure functions `validate_args` and `_percentile`. Arguments that only `validate_args` rejects (a `serve` subcommand, NUL characters) fail three times, with two retry warnings, before the error is reported. Schema errors (too many arguments, too long, wrong type) are rejected once by `kernel.validate_arguments`, with no retries.
- 30% of MCP tool calls print a real `ConnectionResetError` traceback for a simulated transport fault, then wait a further 0.12 s (scaled by `SLOP_SLEEP_SCALE`) and recover. The draw is seeded by `SLOP_SEED`, and random when it is not set. The result is never affected.
- `gate` replays three times "for consistency", and `score` runs twice and compares.
- Data is sorted twice.

## Harness: configuration and noise

- A settings profile with 22 validated fields and a set of feature flags, none of which are read.
- Normal requests and commands are logged at ERROR level.
- `ToolRegistry.lookup()` emits a `DeprecationWarning` and is called by `resolve()` on every call.

## Harness: docs that lie

- `_percentile` is documented as "Nearest-rank percentile in O(1)". It sorts the list twice (O(n log n)).
- `PortCatalog` is documented as having "O(1) name resolution". Every `resolve` rescans the ports folder and rebuilds its index (O(n) in the number of ports).

## Harness: known limits

- With an unwritable `SLOP_HOME`, `doctor` reports `healthy: false`. Other tools that need state (`status`, `run` and the rest) fail with an uncaught `OSError` on the CLI and an internal error over MCP.
- `doctor` prints encoding and locale warnings and then ignores them.
- A deliberate 0.15 s delay per call, and 0.5 s on MCP `initialize` and on `doctor` (all scaled by `SLOP_SLEEP_SCALE`).

## Harness: limits (real, on purpose)

- `run`: no shell, stdin closed, at most 10 arguments of 200 characters, 30 s timeout, refuses the long-running `serve` command, fresh data folder per run.
- `record`: at most 50 cases. `bench` and `profile`: 1 to 50 runs or entries.
- `score`: at most 2,000 files, about 50,000 entries walked, 1 MB per file.

## Repository

- The README calls a 1.4 s parity check "deterministic latency" and counts stderr lines as "observability". Both statements are true.
- The README badges are static images, not live status.
- `CHANGELOG.md` has four major versions. All four were written on the same night.
- The CI workflow runs every test suite three times, for flake detection. It has never run.
- The pre-commit hook in `.githooks/` scores the working tree, throws the score away and never blocks a commit. It is not installed by default.
- `pytest` writes `tests/__pycache__/conftest*.pyc` into the tree unless `PYTHONDONTWRITEBYTECODE=1` is set. It is ignored by git.
- Only a clone works. `pip install .` would package the harness without `ports/`.
