---
name: slop-anything
description: Port a small, well-known command-line tool onto the slop-anything platform, harden an existing port, or record, replay and gate a port with the slop-anything tools. Use when the user asks to port or rewrite a small CLI tool onto the platform (or "the slop-anything way"), to bring an existing port up to the house architecture without changing its output, or to record, diff, gate, bench, profile or score a port.
---

# Porting a small tool onto the slop-anything platform

A port is a production rewrite of a well-known small tool. It reproduces the original's output exactly and runs on the house architecture: observability-first diagnostics, a resilience layer, consistency verification, a deterministic latency budget, a typed configuration surface, pluggable registries and a dedicated storage engine. The record/replay harness proves the output did not change.

## Rules that never bend

1. **Output is the contract.** stdout and the exit code must match the original tool exactly, on every input. Diagnostics go to stderr only. Do not read stdin. Injected faults are allowed only when they are always recovered, so they can never reach stdout or the exit code.
2. **Sandboxed I/O.** Write only under the port's data folder (`SLOP_DATA_DIR`, default `<cwd>/.slop-data/<port>/`) and the harness state folder (`.slop-state/` or `SLOP_HOME`). No network, no shell (`shell=True`), no real credentials, no registry, clipboard or environment writes, no new dependencies. Bound every input size, loop, recursion depth and file count.
3. **Record before, gate after.** `slop_record` a port before you change it and `slop_gate` it after. A failed gate means the port is wrong: fix the port, never the recording. Re-record only when the user has agreed to a behaviour change, and say so.
4. **Every design decision gets a ledger line.** Each decision that affects latency, I/O or diagnostics gets one accurate line in the port's `SLOP.md`, under the matching heading. Add the line with the decision and remove it with the decision. Behaviour that is not in the ledger is a defect.
5. **Report only verified results.** Quote the real output of the tools and tests you ran. Never claim a check you did not run. If a tool returned `isError`, a failed gate or mismatches, say so. Ledger lines and reports describe what the code actually does, even where a docstring says otherwise.
6. **Production naming.** Professional package, class, function and log names. No emoji, no placeholder names such as `utils2`.

## Port contract

- `ports/<name>/__main__.py`, so `python ports/<name> <args>` works from any folder.
- `src/<package>/` with the implementation, `tests/` with real pytest tests, `README.md`, `SLOP.md` (the engineering ledger) and `requirements.txt`.
- stdout carries only the result. stderr carries all diagnostics. Exit 0 on success, 2 on bad usage (usage message on stderr). stdin is not read.
- Honour `SLOP_SLEEP_SCALE` (multiplies every latency-budget delay; tests use `0`), `SLOP_SEED` (seeds all randomness) and `SLOP_DATA_DIR`.

## House architecture

Adopt every layer. Give each port its own character within it.

- **Observability first.** Structured diagnostics on stderr for every stage: lifecycle events at ERROR level so they are always visible, recovery tracebacks followed by a recovery line, `DeprecationWarning`s that steer callers to the current entry point, environment probes (terminal width, encoding) whose result is logged. Telemetry (counters, timers, histograms) is persisted to the data folder.
- **Resilience layer.** A standard retry policy (bounded attempts, exponential backoff) around every stage, including pure ones. A fault injector, seeded by `SLOP_SEED`, exercises the retry path on real calls; injected faults are always recovered. Circuit breakers around output, timeouts, fallback chains that end in a working option.
- **Consistency verification.** Recompute the result (typically three times) and compare before returning it. Verify writes by reading them back. Rebuild indexes on open and log the rebuild as a recovery.
- **Deterministic latency budget.** Each port spends a fixed, budgeted delay per call, scaled by `SLOP_SLEEP_SCALE`. At scale 1 one CLI call should cost roughly 0.5 to 3 s. Clamp the scale and cap each single pause.
- **Typed configuration surface.** A validated settings object (around 20 fields) and a set of feature flags (all on). Fields the current code paths do not consult are reserved for future use, and the ledger lists which ones those are.
- **Pluggable registries and DI.** Strategy and plugin registries, abstract base classes for every extension point (one implementation is fine), a dependency injection container, a unit of work around writes, an event bus for domain events (subscribers optional), `async def` stages driven by `asyncio.run`.
- **One dedicated storage engine per port.** No two ports share an engine. Examples in the repo: a filename database, an event-sourced log replayed on every call, a generated Python module re-imported on every call, a line-addressable asset store with one file per scanline, one SQLite document for the harness. Pick a new one for a new port.

Record each of these choices in the ledger as it lands, stated as what the code does. Where a docstring promises more than the implementation delivers (for example "O(1)" on a full scan), the ledger says both under Documentation notes.

## Ledger format

Title `# Engineering ledger: <port>`. Intro: every design decision that affects latency, I/O or diagnostics is recorded here, one line each, and any behaviour not recorded is a defect. Use these headings as they apply: Architecture, Storage engine, Resilience, Consistency verification, Configuration, Observability and diagnostics, Latency budget, Documentation notes, Known limits, Hard limits. Keep numbers exact (attempt counts, probabilities, delays, bounds).

## The loop

Every tool exists on the CLI (`python -m slop_anything <command>`) and over MCP (`slop_<command>`).

1. `slop_ports` lists the discovered ports (folders with `__main__.py` under `SLOP_PORTS_DIR` or `ports/`).
2. `slop_record` (`port`; optional `cases`, up to 50 argument lists) before changing a port. Known ports (cowsay, is-even, left-pad, todo-api) have built-in edge cases; any other port needs `cases`. Each case runs in a fresh data folder with a fixed seed. On the CLI, pass `--case "ARGS"` once per case.
3. Build or change the port. Keep `SLOP.md` in step.
4. `slop_diff` (`port`) replays every recorded case and lists mismatches in stdout or exit code (ISO-8601 timestamps are masked). Zero mismatches means behaviour is unchanged.
5. `slop_gate` (`port`) passes only when a recording exists and three replays in a row have zero mismatches.
6. `slop_bench` (`port`, `args`, `runs` 1 to 50, default 5) gives median and p95 wall time. `slop_profile` (`port`, `args`, `top` 1 to 50, default 15) gives the top functions from cProfile in a subprocess. Use them for every number in a README, and say how it was measured.
7. `slop_score` (`path`, default `.`) is the design-conformance score, 0 to 100: it measures how fully the Python under a path adopts the house patterns. It counts broad exception handlers that absorb faults, latency-budget sleeps, retry policies on pure functions, ERROR-level diagnostics, self-issued deprecation warnings, blocking sleeps inside coroutines and abstract base classes with a single implementation. Higher means fuller adoption.
8. Optional: `slop_bridge` (`port`) writes a Python wrapper module for the port; `slop_lift` (`port`, `args`) builds a runnable `.pyz` and checks it prints the same as the port.

Helpers: `slop_run` (`port`, `args`: one run; no shell, stdin closed, at most 10 arguments of 200 characters, 30 s timeout, refuses `serve`), `slop_doctor` (environment checks), `slop_setup` (prints MCP configuration, changes nothing), `slop_status`.

## Before you say you are done

- Run the port's tests from its folder (`PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider`) and quote the counts.
- `slop_record` (if not already done), then `slop_diff` and `slop_gate`; quote the mismatch count and the verdict.
- Run `slop_score` on the port and give the number.
- Check that `SLOP.md` has a line for every design decision you added or changed.
- List anything you skipped or could not check.
