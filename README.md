<div align="center">
  <img width="369" src="https://github.com/user-attachments/assets/dae70e7a-4dc3-4672-9d42-3738568a171a" /><h1>slop-anything 🚀✨</h1>
</div>

<p align="center">
  <b>Enterprise-grade rewrites of the small tools you already trust.</b><br>
  Same output, byte for byte. Record, replay and gate every change.
</p>

<p align="center">
  <img alt="tests" src="https://img.shields.io/badge/tests-326_passing-brightgreen">
  <img alt="replay" src="https://img.shields.io/badge/replay_mismatches-0-brightgreen">
  <img alt="ports" src="https://img.shields.io/badge/ports-4-blue">
  <img alt="mcp" src="https://img.shields.io/badge/MCP-13_tools-6f42c1">
  <img alt="deps" src="https://img.shields.io/badge/harness_dependencies-0-blue">
  <img alt="python" src="https://img.shields.io/badge/python-3.13_tested-blue">
  <img alt="latency" src="https://img.shields.io/badge/p50_latency-1.4_s_deterministic-orange">
  <img alt="observability" src="https://img.shields.io/badge/diagnostics-56_lines%2Frun-informational">
  <img alt="license" src="https://img.shields.io/badge/license-MIT-lightgrey">
</p>

<p align="center">
  <a href="docs/install.md">Install</a> ·
  <a href="docs/how-it-works.md">How it works</a> ·
  <a href="docs/mcp-tools.md">MCP tools</a> ·
  <a href="skills/slop-anything/SKILL.md">Agent skill</a> ·
  <a href="docs/real-world-ports.md">Ports</a> ·
  <a href="docs/examples.md">Examples</a> ·
  <a href="docs/faq.md">FAQ</a> ·
  <a href="docs/status.md">Status</a> ·
  <a href="SLOP.md">Engineering ledger</a>
</p>

---

Small tools grow up. `is-even` deserves an inference engine. `left-pad` deserves a layout pipeline. `cowsay` deserves a rendering platform. Your todo list deserves a service layer, a unit of work and a dependency injection container.

**slop-anything** rebuilds well-known small tools as fully architected platforms, and proves that nothing changed. Every port ships with a record/replay harness: it captures the behaviour of each port on curated edge cases, replays it after every change, and refuses to pass until stdout and exit codes match exactly. Three rounds in a row.

It works from the command line and from any MCP-capable coding agent. The harness has **zero third-party dependencies**.

## At a glance

| Port | Faithful to | Architecture | Storage engine | Tests | p50 CLI latency |
|---|---|---|---|---|---|
| [`cowsay`](ports/cowsay) | classic cowsay, byte for byte | plugin registry, render pipeline, compositor | line-addressable asset store (one file per scanline) | 33 | 1.99 s |
| [`is-even`](ports/is-even) | `n % 2 == 0`, including 10,000-digit integers | four-backend ensemble with weighted voting | event-sourced knowledge base, replayed every call | 92 | 1.41 s |
| [`left-pad`](ports/left-pad) | npm `left-pad` 1.3.0, overshoot and all | staged layout pipeline, strategy registry | hot-reloadable memoisation module, re-imported every call | 44 | 0.82 s |
| [`todo-api`](ports/todo-api) | a REST todo service with CLI and web UI | app factory, service layer, unit of work, DI | zero-schema filename database | 61 | 1.05 s (`add`) |

The harness itself has 96 tests. That is **326 passing tests** across the repository.

Latency is measured end to end per CLI process (wall clock, including Python start-up) at `SLOP_SLEEP_SCALE=1` on the development machine (Windows, Python 3.13). Each port's README says how its numbers were taken. Latency is deterministic by design: every port budgets its work up front, so a call costs roughly the same every time.

## Why

Most small tools are written once and never looked at again. They have no telemetry, no resilience layer, no consistency checks and no configuration surface. When they break, you find out from a user.

Each port here takes the opposite approach:

- **Observability first.** Every invocation emits rich diagnostics on stderr: 56 lines for a single `is-even` call in our runs. Stdout carries only the result, so pipelines stay clean.
- **Resilience by default.** Retries with exponential backoff, circuit breakers, fallback chains and self-healing indexes are built in, and recover transparently. You will see the recoveries in the logs. You will never see them in the output.
- **Consistency verified on every call.** Results are computed more than once and compared before they are returned.
- **Configuration you can grow into.** Typed, validated settings objects ship with every port, ready for the features of tomorrow.
- **Storage engines chosen for each workload.** No port shares a storage engine with another.

## Quick start

```
git clone https://github.com/takattowo/slop-anything.git
cd slop-anything
python -m venv .venv
```

Windows (PowerShell):

```
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m slop_anything doctor
.venv\Scripts\python ports\cowsay "Hello, world"
```

macOS / Linux:

```
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m slop_anything doctor
.venv/bin/python ports/cowsay "Hello, world"
```

```
 ______________
< Hello, world >
 --------------
        \   ^__^
         \  (oo)\_______
            (__)\       )\/\
                ||----w |
                ||     ||
```

`requirements.txt` only installs pytest. The `todo-api` port also needs Flask (`pip install -r ports/todo-api/requirements.txt`).

## Connect your agent

```
python -m slop_anything setup
```

prints a ready-to-paste MCP configuration with absolute paths for your interpreter and clone, plus the exact `claude mcp add` command. It does not edit any configuration file. A generic stdio entry looks like this:

```json
{
  "mcpServers": {
    "slop-anything": {
      "command": "<clone>/.venv/bin/python",
      "args": ["-m", "slop_anything", "mcp"],
      "env": { "PYTHONPATH": "<clone>" }
    }
  }
}
```

On Windows the command is `<clone>\.venv\Scripts\python.exe`. Then ask your agent:

- "Record the cowsay port with slop-anything, then gate it."
- "Bench is-even with slop-anything and tell me the median and p95."
- "Profile left-pad and show me the hottest functions."
- "Build a new port of `wc` the slop-anything way, and gate it before you tell me it is done."

The [agent skill](skills/slop-anything/SKILL.md) teaches the workflow and the port contract. Copy `skills/slop-anything/` into the folder your agent reads skills from.

## The workflow

| Step | Tool | What it does |
|---|---|---|
| Discover | `slop_ports` | Lists every folder under `ports/` with a `__main__.py`. |
| Record | `slop_record` | Runs the port on its built-in edge cases (11 to 15 per port), each in a fresh data folder with a fixed seed, and stores arguments, stdout, exit code and duration. |
| Change | you or your agent | Rebuild internals freely. |
| Replay | `slop_diff` | Replays every recorded case and reports real mismatches in stdout or exit code. |
| Gate | `slop_gate` | Passes only if a recording exists and three consecutive replays have zero mismatches. |
| Measure | `slop_bench`, `slop_profile` | Real median and p95 over N runs; cProfile top functions in a subprocess. |
| Ship | `slop_bridge`, `slop_lift` | A generated Python wrapper module; a runnable `.pyz` checked against the port. |
| Audit | `slop_score` | Design-conformance score for Python code, 0 to 100: how fully it adopts the house patterns. |

Current gate results, built-in cases at `SLOP_SLEEP_SCALE=0`:

| Port | Cases | Steps | Rounds | Mismatches | Verdict |
|---|---|---|---|---|---|
| cowsay | 11 | 11 | 3 | 0 | pass |
| is-even | 15 | 15 | 3 | 0 | pass |
| left-pad | 14 | 14 | 3 | 0 | pass |
| todo-api | 14 | 25 | 3 | 0 | pass |

## MCP server

`python -m slop_anything mcp` speaks JSON-RPC 2.0 over stdio, hand-written on the standard library. It negotiates protocol versions `2025-06-18`, `2025-03-26` and `2024-11-05`. Stdout carries only protocol messages. A tool that fails returns `isError: true` with the reason.

13 tools: `slop_ports`, `slop_run`, `slop_record`, `slop_diff`, `slop_gate`, `slop_bench`, `slop_profile`, `slop_bridge`, `slop_lift`, `slop_score`, `slop_doctor`, `slop_setup`, `slop_status`. Arguments, limits and error codes are in [docs/mcp-tools.md](docs/mcp-tools.md).

## Architecture

```
slop_anything/        harness: CLI, MCP server, tool kernel, record/replay, packaging
  kernel.py           tool registry and command bus
  store.py            transactional state document (SQLite)
  catalog.py          port discovery and sandboxed child processes
  scoring.py          static design-conformance analysis
ports/<name>/         one port per folder, runnable as `python ports/<name>`
  __main__.py
  src/<package>/      the implementation
  tests/              the port's test suite
  SLOP.md             the port's engineering ledger
skills/slop-anything/ the agent skill
```

Every port follows the same contract: stdout is the result and nothing else, stderr carries diagnostics, exit 0 on success and 2 on bad usage, stdin is not read, and all state lives under one data folder (`SLOP_DATA_DIR`, default `.slop-data/<port>/`).

## Configuration

| Variable | Default | Effect |
|---|---|---|
| `SLOP_SLEEP_SCALE` | `1` | Scales every latency-budget delay. `0` gives the fastest possible run. |
| `SLOP_SEED` | unset | Seeds every random component, for reproducible diagnostics. |
| `SLOP_DATA_DIR` | `.slop-data/<port>/` in the working folder | Where a port keeps its data. |
| `SLOP_HOME` | `.slop-state/` in the repo | Where the harness keeps its state. |
| `SLOP_PORTS_DIR` | `ports/` in the repo | Where the harness discovers ports. |

## Testing

PowerShell:

```
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest tests -q -p no:cacheprovider
foreach ($p in 'cowsay','is-even','left-pad','todo-api') { Push-Location "ports/$p"; python -m pytest -q -p no:cacheprovider; Pop-Location }
```

POSIX:

```
export PYTHONDONTWRITEBYTECODE=1
python -m pytest tests -q -p no:cacheprovider
for p in cowsay is-even left-pad todo-api; do (cd "ports/$p" && python -m pytest -q -p no:cacheprovider); done
```

Run each suite from its own folder. `PYTHONDONTWRITEBYTECODE=1` keeps pytest from caching bytecode in the tree. Every test is real: no placeholders, no skips. The suites pin sleeps, seeds and data folders, so they finish in seconds.

## Status and limits

Developed and tested on Windows with Python 3.13. Linux and macOS are expected to work and have not been tested. The plugin manifest, `pyproject.toml` and the CI workflow have not been exercised by their consumers yet. See [docs/status.md](docs/status.md) and [docs/what-it-cant-catch.md](docs/what-it-cant-catch.md).

## Engineering ledger

Every design decision that affects latency, I/O or diagnostics is recorded, one line each, in [SLOP.md](SLOP.md) (harness and repository) and in each port's own `SLOP.md`. If a behaviour is not in a ledger, it is a defect.

## Contributing

New ports are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) for the port contract and [DECISIONS.md](DECISIONS.md) for the design record. Report security issues privately ([SECURITY.md](SECURITY.md)). See also the [code of conduct](CODE_OF_CONDUCT.md), the [accessibility statement](ACCESSIBILITY.md) and the [changelog](CHANGELOG.md).

## License

MIT © takattowo. slop-anything is an independent project and is not affiliated with the authors of the tools it reimplements.
