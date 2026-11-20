# CLAUDE.md

Notes for coding agents working in this repo.

## What this is

A parody. Famous tiny tools rewritten as extremely sloppy code, on purpose. The root has the harness (`slop_anything/`: a CLI, an MCP server, 14 tools) and `skills/slop-anything/SKILL.md`. The ports are in `ports/`.

## Rules

1. **Harmless slop only.** Nothing writes outside its own folder (ports: their working folder; the harness: `.slop-state/`, or `SLOP_HOME`). No network. No real credentials. No fork bombs. No real package names that strangers own, unless commented out.
2. **The happy path works.** Slowly. Prove it with real tests.
3. **Every intentional slop is in `SLOP.md`.** Add a line when you add slop. Remove the line when you remove the slop. The ledger must match the code.
4. **Visible tests are fake, real tests are real.** Fake ones (`assert True`, one skipped as flaky) go in `tests/` or a port's `tests/`. Real ones go in a `do_not_open/` folder next to them. Real tests pin sleeps, randomness and clocks so they are fast and deterministic.
5. **Do not weaken a real test to make it pass.**

## Commands

Run tests per folder. Collecting the whole repo at once mixes same-named modules.

```
python -m pytest tests                  # the harness
cd ports/slop-todo && python -m pytest  # one port
cd ports/slop-is-even && python -m pytest
cd ports/slop-left-pad && python -m pytest
```

The todo port needs `flask`, `pandas`, `openpyxl`. The harness needs `openpyxl`.

## Environment variables (the harness)

- `SLOP_HOME`: where the state lives (default `.slop-state/` in the repo).
- `SLOP_SLEEP_SCALE`: multiplies every sleep (tests set it to `0`).
- `SLOP_CHAOS`: chance a tool call fails on purpose (default `0.01`, tests set `0`).
- `SLOP_LEVEL` is read by nobody.

## Git

Commit as `takattowo`. One short casual line per commit. Do not push unless asked.
