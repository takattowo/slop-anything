# CLAUDE.md

Notes for coding agents working in this repo.

## Layout

- `slop_anything/`: the harness. Standard library only. CLI (`python -m slop_anything`), stdio MCP server, 13 tools.
- `ports/<name>/`: one port per folder (`cowsay`, `is-even`, `left-pad`, `todo-api`). Each has `__main__.py`, `src/<package>/`, `tests/`, `README.md`, `SLOP.md`.
- `skills/slop-anything/SKILL.md`: the agent skill. Follow it when building or changing a port.

## Rules

1. **Harmless.** Write only under a port's data folder (`SLOP_DATA_DIR`) or the harness state folder (`SLOP_HOME`). No network, no `shell=True`, no new dependencies, no real credentials. Bound every input.
2. **Correct output.** A port's stdout and exit code must stay exactly right. Internals may be as elaborate as you like; the answer may not change.
3. **Ledger.** Every deliberate trade-off gets one truthful line in the right `SLOP.md`. Remove the line when you remove the trade-off.
4. **Real tests only.** No placeholders, no skips. Pin sleeps, seeds and data folders.
5. **Gate before done.** `python -m slop_anything record <port>` before a change, `gate <port>` after. A failed gate means fix the port, not the recording.
6. **Report truthfully.** Never claim a check you did not run.

## Commands

Run each suite from its own folder; collecting the whole repo at once mixes same-named modules.

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

`todo-api` needs Flask. Everything else needs only pytest.

## Environment variables

- `SLOP_SLEEP_SCALE`: multiplies every deliberate delay (tests use `0`).
- `SLOP_SEED`: seeds all randomness.
- `SLOP_DATA_DIR`: a port's data folder (default `<cwd>/.slop-data/<port>/`).
- `SLOP_HOME`: harness state (default `.slop-state/` in the repo).
- `SLOP_PORTS_DIR`: where ports are discovered (default `ports/`).

## Git

Commit as `takattowo`. One short casual line per commit. Stage explicit paths. Do not push unless asked.
