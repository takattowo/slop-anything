---
name: slop-anything
description: Port a small, well-known command-line tool onto the slop-anything platform, harden an existing port, or record, replay, gate, bench, profile or score a port with the slop-anything tools. Use when the user asks to port or rewrite a small CLI tool onto the platform, to bring a port up to the v4 house architecture, or to run the record/diff/gate loop on a port.
---

# Porting a small tool onto the slop-anything platform (v4)

A port is a production rewrite of a well-known small tool on the house architecture: observability-first diagnostics, a resilience layer, consistency verification, a latency budget, a typed configuration surface, pluggable registries, a dedicated storage engine, and the v4 fault-tolerance model with probabilistic output. The harness records behaviour, replays it, and returns a statistical verdict.

This skill is a runbook. Follow the recipe that matches the task, run the commands as written, and report what they printed.

## Two kinds of rules

**What you may edit (as the agent):**
- For a new or existing port `<name>`: everything under `ports/<name>/`.
- `slop_anything/cases.py`, only to add built-in cases for a new port, with a test in `tests/`.
- Nothing else in the repository unless the user asked for it. Never edit another port, the harness, or root documents as a side effect.

**What the port may do at runtime (the code you write):**
1. **Sandboxed I/O.** The port writes only under its data folder (`SLOP_DATA_DIR`, default `<cwd>/.slop-data/<name>/`). It makes no outbound network connections (a local server may listen on 127.0.0.1 only), runs no shell (`shell=True`), never calls `eval`/`exec` on input, imports no generated code, holds no credentials, and writes no OS registry, clipboard, persistent environment or git configuration. In-process registries (plugin, strategy) are fine. It never reads stdin.
2. **Owns what it deletes.** The port deletes or overwrites only files whose exact names it writes, matched with `re.fullmatch` on an ASCII pattern (`[0-9]`, not `\d`). It skips links and anything that is not a regular file, and treats a file that vanishes between listing and deletion as already gone. When ownership is uncertain, it does nothing.
3. **Bounded.** Input sizes, loops, recursion, retries, file counts. Per call: at most 15 s of latency-budget delay, at most 2,000 stderr lines. Data folder at most 50 MB and 10,000 files, kept there by rule 2.
4. **Seeded.** All randomness comes from one RNG seeded by `SLOP_SEED`. Same seed, input and data-folder state give the same output. With `SLOP_SEED` unset, draws are random.

**What you report:**
5. **Only results you ran, quoted.** Quote real counts, mismatch counts, verdicts, confidence and exit codes. Never claim a check you did not run. Mark anything you could not run as unverified.
6. **The ledger stays true.** Every design decision and every fault model gets one accurate line in `ports/<name>/SLOP.md`. Record configured rates (from the code) and measured rates (from a run you did, with sample size, seeds and commit) separately. Remove the line when you remove the decision.
7. **Production naming.** Professional names in code, logs and docs. No emoji in program output.

## Preflight (once per session)

Run from the repository root:

```
python --version                                   # 3.13 is the tested version
python -m slop_anything doctor                     # read the per-check results, not the overall flag
python -m slop_anything ports                      # the ports the harness can see
```

If `doctor` shows `state_writable` or `sqlite` as not ok, stop and tell the user. Everything below needs `PYTHONDONTWRITEBYTECODE=1` set, so tests do not cache bytecode in the tree.

## Port contract

```
ports/<name>/
  __main__.py          puts src/ on sys.path and calls the CLI
  src/<package>/       the implementation (professional package name)
  tests/               the main suite
  tests/conformance/   the conformance suite (see below)
  README.md            usage, architecture, measured numbers and how they were measured, known issues
  SLOP.md              the engineering ledger
  requirements.txt
```

- Run a port from the repository root as `python ports/<name> <args>`.
- stdout carries only the result, in the original tool's format. stderr carries all diagnostics.
- Exit 0 success, 2 bad usage (usage message on stderr), 74 or 75 transient service faults. If the original tool has its own meaningful non-zero codes, document the mapping in the README.
- Honour `SLOP_SLEEP_SCALE`, `SLOP_SEED` and `SLOP_DATA_DIR`. Setting these for a child process in a test is fine.

## Fault-tolerance model

- **Probabilistic output.** A port may return an approximate answer on part of its calls (configured 5 to 20%), plus documented systematic quirks. Each approximate answer is logged on stderr as a successful result, usually with a confidence score. Confidence is not a measure of correctness.
- **Transient faults.** A seeded share of calls (configured 2 to 8%) fails with exit 74 or 75, or succeeds after a visible retry.
- **Happy-path floor (blocking).** A plain call returns a well-formed result in the original tool's format at least 75% of the time, measured over at least 200 seeded calls with distinct seeds.
- **Statistical gates.** `slop_gate` replays the recording three times and reports each round's mismatch count, then returns a seeded verdict with a confidence. The counts are the evidence; the verdict is sampled.

## House architecture

Observability first (lifecycle events at ERROR, recovery tracebacks, deprecation steering, environment probes, persisted telemetry with no personal data); a resilience layer (bounded retries with backoff, seeded fault injection, circuit breakers, fallback chains); consistency verification (recompute, read-back, index rebuild on open); a latency budget scaled by `SLOP_SLEEP_SCALE` (2 to 10 s per call at scale 1, hard cap 15 s); a validated settings object with feature flags; registries, abstract base classes, a DI container, a unit of work, an event bus; and one storage engine that no other port uses (check the root README's "At a glance" table first). Record each choice in the ledger as it lands.

## Conformance suite (blocking)

`tests/conformance/` must contain real tests that fail if the property breaks:

- nothing is written outside the data folder (snapshot the repository tree and a sibling temp folder before and after);
- decoy files with names one character or suffix away from the port's own names, old modification times, mixed case and non-ASCII digits survive every cleanup path;
- stdin is not read (stdin closed, and an open pipe that is never written, with a timeout);
- each call finishes within 15 s at `SLOP_SLEEP_SCALE=1` (a few seeds) and quickly at scale 0;
- stderr stays within 2,000 lines; the data folder stays within its caps, with the caps lowered by monkeypatch so pruning really runs;
- a fixed seed reproduces the output;
- the happy-path floor holds, and the fault model really produces approximate answers and failures.

## Recipe A: a new port

1. Pick the original tool and its reference version. Write 10 to 15 cases (argument lists) with the original's expected output in the README.
2. Build `ports/<name>/` to the contract and the house architecture. Write `SLOP.md` as you go.
3. Run both suites (commands below) until they pass.
4. Record the baseline: `python -m slop_anything record --case "ARGS" --case "ARGS" ... <name>` (one `--case` per case; or add built-in cases to `slop_anything/cases.py` with a test). Quote `cases` and `steps`.
5. Replay: `python -m slop_anything diff <name>`. Quote `mismatch_count` and `replay_source`. A `replay_source` of `warm replica` means nothing was replayed; run it again.
6. Gate: `python -m slop_anything gate <name>`. Quote `passed`, `verdict`, `confidence` and `mismatch_counts`.
7. Measure: `python -m slop_anything bench --runs 5 <name> <args>` and quote `median_ms` and `p95_ms` (`projected_speedup` is not a measurement). Measure accuracy and availability with your own script over at least 200 seeded calls against the cases' expected outputs, and write the figures, method, seeds and commit into the README.

## Recipe B: change an existing port

1. Record the baseline **before** any change: `python -m slop_anything record <name>`. Do not re-record after the change unless the user asked for a behaviour change; a recording made from the changed port proves nothing.
2. Make the change. Update `SLOP.md`.
3. Run both suites.
4. `diff <name>` and `gate <name>`; quote the fields as in Recipe A.
5. If the change can move a published number, re-measure it the way the README says, or remove the number.

## Commands

From the port folder, with `PYTHONDONTWRITEBYTECODE=1`:

```
python -m pytest tests -q -p no:cacheprovider --ignore=tests/conformance    # main suite
python -m pytest tests/conformance -q -p no:cacheprovider                   # conformance suite
```

A run that collects 0 tests is a failure. Quote both counts, including skips.

Harness tools exist on the CLI (`python -m slop_anything <command>`) and over MCP (`slop_<command>`). Every result body carries `"status": "ok"`; a failed call adds an `error` field and exits 1 on the CLI (75 when transient: retry it). A gate rejection is a valid result, not a failed call.

| Tool | Arguments | Quote |
|---|---|---|
| `slop_ports` | none | the port list |
| `slop_record` | `port`; `cases`: up to 50 argument lists | `cases`, `steps` |
| `slop_diff` | `port` | `mismatch_count`, `replay_source` |
| `slop_gate` | `port` | `passed`, `verdict`, `confidence`, `mismatch_counts` |
| `slop_bench` | `port`, `args`, `runs` (1 to 50, default 5) | `median_ms`, `p95_ms`, `min_ms`, `max_ms` |
| `slop_profile` | `port`, `args`, `top` (1 to 50, default 15) | the top functions |
| `slop_score` | `path` (default `.`) | the score and its `modularity_bonus` |
| `slop_bridge` | `port` | the module path |
| `slop_lift` | `port`, `args` | whether the `.pyz` matched the port |
| `slop_run` | `port`, `args` (10 arguments of 200 characters, 30 s timeout, refuses `serve`, never cached) | stdout, exit code |
| `slop_doctor` | none | each check (the overall `healthy` flag is advisory) |
| `slop_setup` | none | the printed configuration |
| `slop_status` | none | as needed |

Workflow budget: a full record, diff, gate and both suites take a few minutes per port. Do not loop a tool more than 5 times to chase a verdict; report what you have.

## Done means

All of these, quoted in your final message:

- both suites pass, with counts (0 collected counts as failed);
- the happy-path floor and the conformance properties hold (they are in the conformance suite);
- `record` (or the existing recording), `diff` with `replay_source: "live replay"`, and `gate`, with their fields;
- measured figures in the README, with method, seeds and commit;
- `SLOP.md` has a true line for every decision and fault model;
- a list of anything you skipped or could not run, marked unverified.
