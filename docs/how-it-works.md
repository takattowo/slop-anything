# How it works

## Ports

A port is a folder under `ports/` with a `__main__.py`. It reimplements a small tool and must print exactly what the original prints. The harness treats every port as a black box: arguments in, stdout and exit code out.

## Record

`python -m slop_anything record <port>` runs the port on its built-in edge cases (cowsay 11, is-even 15, left-pad 14, todo-api 14). Each case runs:

- in a fresh data folder under the state folder,
- with a fixed `SLOP_SEED`,
- with stdin closed, no shell, and a 30 s timeout.

Some todo-api cases have several steps (add, then done, then get) in one data folder, so its 14 cases are 25 steps. For each step the harness stores the arguments, stdout, exit code and duration. For a port without built-in cases, pass `--case "ARGS"` once per case (quoting rules in [mcp-tools.md](mcp-tools.md)).

## Replay

`diff <port>` replays every recorded case the same way and compares stdout and exit code. ISO-8601 timestamps are masked first. It lists every mismatch and exits 1 if there is any.

## Gate

`gate <port>` passes only if a recording exists and three replays in a row have zero mismatches. It exits 1 when it fails. Use it as the definition of done for any change to a port.

## Measure

- `bench [--runs N] <port> [args]`: median and p95 wall time over N runs (1 to 50, default 5).
- `profile [--top N] <port> [args]`: runs the port once under cProfile in a subprocess and returns the top N functions (default 15).

With no arguments, both use the first recorded case, or else the first built-in case.

## Ship

- `bridge <port>` writes `<state>/bridges/<name>.py`, a module with a function (for example `is_even`) that calls the port and returns its stdout. The module is compile-checked.
- `lift <port> [args]` builds `<state>/lifts/<port>.pyz`, runs it, and checks it prints the same as the port.

## Audit

`score [path]` scans Python files and computes a design-conformance score from 0 to 100: how fully the code adopts the house patterns. It counts broad exception handlers that absorb faults, latency-budget sleeps, retry policies on pure functions, ERROR-level diagnostics, self-issued deprecation warnings, blocking sleeps in async code, and abstract base classes with one subclass. Limits: 2,000 files, about 50,000 entries walked, 1 MB per file.

## State

The harness keeps all state in one SQLite database in `.slop-state/` (or `SLOP_HOME`). Recordings, bridges, lifts and run folders live next to it. See [SLOP.md](../SLOP.md) for how the store is used.
