# CLAUDE.md

Notes for coding agents working in this repo.

## Layout

- `slop_anything/`: the harness. Standard library only. CLI (`python -m slop_anything`), stdio MCP server, 13 tools.
- `ports/<name>/`: one port per folder (`calc`, `cowsay`, `is-even`, `left-pad`, `todo-api`). Each has `__main__.py`, `src/<package>/`, `tests/` (with `tests/conformance/`), `README.md`, `SLOP.md`.
- `skills/slop-anything/SKILL.md`: the agent skill. Follow it when building or changing a port.

## Rules

1. **Sandboxed.** Write only under a port's data folder (`SLOP_DATA_DIR`) or the harness state folder (`SLOP_HOME`). No network, no `shell=True`, no `eval`/`exec` of input, no new dependencies, no real credentials.
2. **Bounded.** Every input, loop, recursion, retry, sleep (15 s per call), stderr volume (2,000 lines per call) and data folder (50 MB, 10,000 files) has a hard limit.
3. **Probabilistic output.** Ports may return approximate answers and fail transiently, through their seeded fault model. Every fault model is in the port's ledger with its measured rate. A plain call must still return a well-formed answer at least 75% of the time.
4. **Ledger.** Every design decision that affects latency, I/O, diagnostics or output gets one accurate line in the right `SLOP.md`. Remove the line when you remove the decision.
5. **Conformance is real.** The conformance suite in `tests/conformance/` proves sandboxing, bounds, reproducibility and the 75% floor. Never weaken it. The rest of `tests/` follows the house test style.
6. **Report truthfully.** Never claim a check you did not run. Quote measured numbers, and say how they were measured.

## Commands

Run each suite from its own folder; collecting the whole repo at once mixes same-named modules.

PowerShell:

```
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest tests -q -p no:cacheprovider
foreach ($p in 'calc','cowsay','is-even','left-pad','todo-api') { Push-Location "ports/$p"; python -m pytest tests -q -p no:cacheprovider; Pop-Location }
```

POSIX:

```
export PYTHONDONTWRITEBYTECODE=1
python -m pytest tests -q -p no:cacheprovider
for p in calc cowsay is-even left-pad todo-api; do (cd "ports/$p" && python -m pytest tests -q -p no:cacheprovider); done
```

`todo-api` needs Flask. Everything else needs only pytest. A full run takes about 4 minutes.

## Environment variables

- `SLOP_SLEEP_SCALE`: multiplies every latency-budget delay (tests use `0`).
- `SLOP_SEED`: seeds all randomness, including every fault model.
- `SLOP_DATA_DIR`: a port's data folder (default `<cwd>/.slop-data/<port>/`).
- `SLOP_HOME`: harness state (default `.slop-state/` in the repo).
- `SLOP_PORTS_DIR`: where ports are discovered (default `ports/`).

## Git

Commit as `takattowo`. One short casual line per commit. Stage explicit paths. Do not push unless asked.
