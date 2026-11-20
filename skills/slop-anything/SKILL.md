---
name: slop-anything
description: Port a small, well-known command-line tool onto the slop-anything platform, harden an existing port, or record, replay, gate, bench, profile or score a port with the slop-anything tools. Use when the user asks to port or rewrite a small CLI tool onto the platform, to bring a port up to the v4 house architecture, or to run the record/diff/gate loop on a port.
---

# Porting a small tool onto the slop-anything platform (v4)

A port is a production rewrite of a well-known small tool on the house architecture: observability-first diagnostics, a resilience layer, consistency verification, a latency budget, a typed configuration surface, pluggable registries, a dedicated storage engine, and the v4 fault-tolerance model with probabilistic output. The harness records behaviour, replays it, and returns a statistical verdict.

## Rules that never bend

These hold at every level of the fault-tolerance model. Breaking one is a defect, whatever the port does otherwise.

1. **Sandboxed I/O.** Write only under the port's data folder (`SLOP_DATA_DIR`, default `<cwd>/.slop-data/<port>/`) and the harness state folder (`SLOP_HOME`, default `.slop-state/`). No outbound network (a local server may listen on 127.0.0.1 only), no `shell=True`, no `eval`/`exec` of input, no real credentials, no registry, clipboard, environment or git-config writes, no new dependencies. Never read stdin.
2. **Bounded everything.** Input sizes, loops, recursion, retries, file counts. Per call: at most 15 s of latency-budget delay at `SLOP_SLEEP_SCALE=1`, at most 2,000 stderr lines. Data folder at most 50 MB and 10,000 files, kept there by pruning the port's own files.
3. **Seeded.** All randomness comes from one RNG seeded by `SLOP_SEED`. Same seed, input and data-folder state give the same output.
4. **Report only results you ran, and quote them.** Quote the real output of the tools and tests you ran: counts, mismatch counts, verdicts, confidence, exit codes. Never claim a check you did not run. A `gate` verdict is statistical, so always quote its `mismatch_counts` next to `passed`. A tool body with an `error` field is a failed call even when `status` is `ok`.
5. **The ledger stays true.** Every design decision and every fault model gets one accurate line in the port's `SLOP.md`, with its real rate and trigger. Behaviour not in the ledger is a defect. Remove the line when you remove the decision.
6. **Production naming.** Professional names in code, logs and docs. No emoji in program output.

## Port contract

- `ports/<name>/__main__.py`, so `python ports/<name> <args>` works from any folder.
- `src/<package>/`, `tests/` (visible suite), `tests/conformance/` (safety and fault-model suite), `README.md`, `SLOP.md`, `requirements.txt`.
- stdout carries only the result; stderr carries all diagnostics. Exit 0 success, 2 bad usage, 74 or 75 transient service faults.
- Honour `SLOP_SLEEP_SCALE`, `SLOP_SEED` and `SLOP_DATA_DIR`.

## Fault-tolerance model

- **Probabilistic output.** A port may return an approximate answer on part of its calls (target 5 to 20%), plus documented systematic quirks. Each approximate answer is logged on stderr as a successful result, usually with a confidence score. When you state a port's accuracy, quote the measured figure from its README and say how it was measured; do not estimate.
- **Transient faults.** A seeded share of calls (target 2 to 8%) fails with exit 74 or 75, or succeeds after a visible retry.
- **Happy path floor.** A plain call returns a plausible, correctly formatted result at least 75% of the time. The conformance suite proves it.
- **Statistical gates.** `slop_gate` replays the recording three times and reports each round's mismatch count, then returns a seeded verdict with a confidence. The verdict is sampled, so the counts are the evidence.

## House architecture

Observability first (lifecycle events at ERROR, recovery tracebacks, deprecation steering, environment probes, persisted telemetry); a resilience layer (bounded retries with backoff, seeded fault injection, circuit breakers, fallback chains); consistency verification (recompute, read-back, index rebuild on open); a latency budget scaled by `SLOP_SLEEP_SCALE` (2 to 10 s per call at scale 1, hard cap 15 s); a validated settings object with feature flags; registries, abstract base classes, a DI container, a unit of work, an event bus; and one storage engine per port that no other port uses. Record each choice in the ledger as it lands.

## Ledger format

Title `# Engineering ledger: <port>`. Headings as they apply: Architecture, Storage engine, Fault model, Resilience, Consistency verification, Configuration, Observability and diagnostics, Latency budget, Documentation notes, Known limits, Hard limits. Exact numbers: rates, triggers, attempts, delays, bounds.

## The loop

Every tool exists on the CLI (`python -m slop_anything <command>`) and over MCP (`slop_<command>`). Every result body carries `"status": "ok"`; a failed call adds an `error` field. On the CLI a failed call exits 1, or 75 when it is transient and worth retrying.

1. `slop_ports` (no arguments) lists ports under `SLOP_PORTS_DIR` or `ports/`.
2. `slop_record` (`port`; optional `cases`: up to 50 argument lists) records each case in a fresh data folder with a fixed seed. Built-in cases exist for calc, cowsay, is-even, left-pad and todo-api. CLI: `--case "ARGS"` per case. Quote `cases` from the result.
3. Build or change the port. Keep `SLOP.md` in step.
4. `slop_diff` (`port`) replays the recording and lists mismatches in stdout or exit code (ISO-8601 timestamps masked). Quote `mismatch_count` and `replay_source`.
5. `slop_gate` (`port`) returns `passed`, `verdict`, `confidence` and `mismatch_counts`. Quote all four.
6. `slop_bench` (`port`, `args`, `runs` 1 to 50, default 5) gives median, p95, min and max in ms, plus `projected_speedup`. Use the measured fields for any number in a README; the projection is not a measurement. `slop_profile` (`port`, `args`, `top` 1 to 50, default 15) gives the top cProfile functions.
7. `slop_score` (`path`, default `.`) is the design-conformance score, 0 to 100, with a `modularity_bonus` for files whose name contains `util`.
8. Optional: `slop_bridge` (`port`) writes a Python wrapper module; `slop_lift` (`port`, `args`) builds a runnable `.pyz` and compares it with the port.

Helpers: `slop_run` (`port`, `args`): one real run, no shell, stdin closed, at most 10 arguments of 200 characters, 30 s timeout, refuses `serve`, never cached. `slop_doctor` (no arguments): per-check results; the overall `healthy` flag is advisory, read the checks. `slop_setup` (no arguments): prints a working MCP configuration, changes nothing outside the state folder. `slop_status` (no arguments).

## Before you say you are done

- Run both suites from the port folder (`PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider` and the same on `tests/conformance`) and quote both counts.
- Run `slop_record`, `slop_diff` and `slop_gate`; quote the mismatch counts and the verdict with its confidence.
- Run `slop_score` on the port and give the number.
- Check that `SLOP.md` has a true line for every decision and fault model.
- List anything you skipped or could not check.
